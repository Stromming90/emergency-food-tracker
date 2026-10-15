package win.strommingflix.eft;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

/**
 * Emergency Food Storage Tracker — Android app.
 * A WebView wrapper around the self-hosted web UI, with camera access so the
 * site's barcode scanning (BarcodeDetector) works. The web app detects the
 * "EFT-Android" user-agent token to show the scan buttons.
 */
public class MainActivity extends Activity {

    private static final int REQ_CAMERA = 100;
    private static final String PREFS = "eft";
    private static final String KEY_URL = "server_url";
    private static final String APP_VERSION = "2.8.0";
    // Custom deep-link scheme: an OIDC flow that somehow ends up in the
    // browser redirects back into the app via win.strommingflix.eft://…
    private static final String DL_SCHEME = "win.strommingflix.eft";

    private WebView web;
    private PermissionRequest pendingPerm;
    private String serverUrl;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        serverUrl = prefs.getString(KEY_URL, null);
        if (serverUrl == null || serverUrl.isEmpty()) showSetup();
        else showWeb();
        handleOidcLink(getIntent());
        // Camera is needed for barcode scanning.
        if (checkSelfPermission(Manifest.permission.CAMERA)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAMERA);
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleOidcLink(intent);
    }

    /**
     * If we were opened via the deep link
     * win.strommingflix.eft://oidc/callback?code=…&state=…, replay it against
     * the server inside the WebView: the code/state exchange happens
     * server-side, so the session cookie lands in the app.
     */
    private void handleOidcLink(Intent intent) {
        if (intent == null || intent.getData() == null) return;
        Uri data = intent.getData();
        if (!DL_SCHEME.equals(data.getScheme()) || serverUrl == null) return;
        Uri server = Uri.parse(serverUrl);
        Uri target = new Uri.Builder()
                .scheme(server.getScheme())
                .encodedAuthority(server.getEncodedAuthority())
                .path("/api/oidc/callback")
                .encodedQuery(data.getEncodedQuery())
                .build();
        if (web != null) {
            web.loadUrl(target.toString());
        } else {
            showWeb();
            if (web != null) web.loadUrl(target.toString());
        }
    }

    // ---------------- first-run: enter the server URL ----------------
    private void showSetup() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setPadding(48, 48, 48, 48);
        box.setBackgroundColor(0xFF10151C);

        TextView title = new TextView(this);
        title.setText("🥫 Emergency Food Storage");
        title.setTextSize(22);
        title.setGravity(Gravity.CENTER);
        title.setPadding(0, 0, 0, 8);
        title.setTextColor(0xFFF2F5F7);

        TextView sub = new TextView(this);
        sub.setText("Enter the address of your tracker server:");
        sub.setGravity(Gravity.CENTER);
        sub.setPadding(0, 0, 0, 24);
        sub.setTextColor(0xFF9AA7B0);

        final EditText input = new EditText(this);
        input.setHint("https://eft.example.com");
        input.setText("https://");
        input.setTextColor(0xFFF2F5F7);
        input.setHintTextColor(0xFF6B7A85);
        input.setHighlightColor(0xFF3B82F6);

        Button go = new Button(this);
        go.setText("Open");
        go.setOnClickListener(v -> {
            String url = input.getText().toString().trim();
            if (!url.startsWith("http")) {
                url = "https://" + url;
            }
            Uri uri = Uri.parse(url);
            String scheme = uri.getScheme();
            if (scheme == null || !(scheme.equals("http") || scheme.equals("https"))
                    || uri.getHost() == null) {
                Toast.makeText(this, "Please enter a valid server address",
                        Toast.LENGTH_SHORT).show();
                return;
            }
            serverUrl = uri.buildUpon().path("").build().toString();
            getSharedPreferences(PREFS, MODE_PRIVATE)
                    .edit().putString(KEY_URL, serverUrl).apply();
            showWeb();
        });

        box.addView(title);
        box.addView(sub);
        box.addView(input);
        box.addView(go);

        TextView ver = new TextView(this);
        ver.setText("App v" + APP_VERSION);
        ver.setTextSize(12);
        ver.setGravity(Gravity.CENTER);
        ver.setPadding(0, 24, 0, 0);
        ver.setTextColor(0xFF6B7A85);
        box.addView(ver);

        setContentView(box);
    }

    // ---------------- the web app ----------------
    private void showWeb() {
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        // Token used by the web app to enable the scan buttons.
        s.setUserAgentString(s.getUserAgentString() + " EFT-Android/2.8.0");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri uri = req.getUrl();
                String scheme = uri.getScheme() == null ? "" : uri.getScheme();
                // Keep ALL http/https navigation inside the WebView — including
                // the SSO/OIDC provider (e.g. Keycloak) — so the login session
                // cookie stays with the app and it returns to the app when done.
                if (scheme.equals("http") || scheme.equals("https")) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                } catch (Exception ignored) { }
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                for (String r : request.getResources()) {
                    if (r.equals(PermissionRequest.RESOURCE_VIDEO_CAPTURE)) {
                        if (checkSelfPermission(Manifest.permission.CAMERA)
                                == PackageManager.PERMISSION_GRANTED) {
                            request.grant(request.getResources());
                        } else {
                            pendingPerm = request; // granted in onRequestPermissionsResult
                            requestPermissions(
                                    new String[]{Manifest.permission.CAMERA}, REQ_CAMERA);
                        }
                        return;
                    }
                }
                request.deny();
            }
        });

        CookieManager.getInstance().setAcceptCookie(true);
        web.loadUrl(serverUrl);
        setContentView(web, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] results) {
        super.onRequestPermissionsResult(code, perms, results);
        if (code == REQ_CAMERA && pendingPerm != null) {
            if (results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) {
                pendingPerm.grant(pendingPerm.getResources());
            } else {
                pendingPerm.deny();
                Toast.makeText(this,
                        "Camera permission is needed for barcode scanning",
                        Toast.LENGTH_LONG).show();
            }
            pendingPerm = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }
}
