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
 * "EFT-Android" user-agent token to show the scan button.
 */
public class MainActivity extends Activity {

    private static final int REQ_CAMERA = 100;
    private static final String PREFS = "eft";
    private static final String KEY_URL = "server_url";

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
        // Camera is needed for barcode scanning.
        if (checkSelfPermission(Manifest.permission.CAMERA)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAMERA);
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

        TextView sub = new TextView(this);
        sub.setText("Enter the address of your tracker server:");
        sub.setGravity(Gravity.CENTER);
        sub.setPadding(0, 0, 0, 24);

        final EditText input = new EditText(this);
        input.setHint("https://eft.example.com");
        input.setText("https://");

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
        // Token used by the web app to enable the scan button.
        s.setUserAgentString(s.getUserAgentString() + " EFT-Android/2.7");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri uri = req.getUrl();
                String host = Uri.parse(serverUrl).getHost();
                if (host != null && host.equals(uri.getHost())) return false;
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
