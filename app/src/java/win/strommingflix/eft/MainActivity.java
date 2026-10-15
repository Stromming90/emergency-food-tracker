package win.strommingflix.eft;

import android.Manifest;
import android.app.AlertDialog;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.SharedPreferences;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ComponentName;
import android.os.Build;
import android.provider.Settings;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
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
import android.os.Looper;
import android.widget.Toast;

/**
 * Emergency Food Storage Tracker — Android app.
 * A WebView wrapper around the self-hosted web UI, with camera access so the
 * site's barcode scanning (BarcodeDetector) works. The web app detects the
 * "EFT-Android" user-agent token to show the scan buttons.
 *
 * v2.12.0: native notifications — a periodic JobScheduler job
 * (PollJobService) polls the server for expiring items and raises
 * system notifications even when the app is closed.
 *
 * v2.12.1: in-app updates — a DownloadListener hands APK downloads to
 * the system DownloadManager, so the web UI's "Download update" link
 * downloads the new APK and tapping the system notification opens the
 * installer (installs over the current app; same signing key).
 *
 * v2.12.6: poll-on-open — the web UI now calls EFTNative.pollNow()
 * when it boots, so a background check runs immediately after the app
 * opens (and after login), instead of waiting up to 30 minutes. The
 * test button and pollNow post their work to the main thread and
 * report failures with a visible toast + CrashLog, so nothing fails
 * silently. This fixes "Last check: HTTP 401" (the poll ran while the
 * session had expired; now it re-runs right after login).
 *
 * v2.12.5: ACCESS_NETWORK_STATE added — JobScheduler rejects jobs
 * with a connectivity constraint without it (SecurityException on
 * Android 16; the background notification job therefore never
 * existed on that device). Also: the update dialog's browser buttons
 * now go through EFTNative.openUrl (ACTION_VIEW outside the WebView)
 * instead of intent:// anchor clicks, which did nothing on that
 * device's WebView, and every failure raises a visible toast.
 *
 * v2.12.4: the in-app update download now bypasses the system
 * DownloadManager entirely (it silently failed on at least one real
 * device). The app downloads /app.apk itself with HttpURLConnection
 * into its own storage and hands the file straight to the package
 * installer through a tiny content provider (APKProvider) — the
 * result is recorded, toasted and reported through the EFTNative
 * bridge, so failures are visible instead of silent. The web UI also
 * always offers the browser-download fallback inside the app.
 *
 * v2.12.3: notifications actually start — the manifest was missing
 * RECEIVE_BOOT_COMPLETED, which JobScheduler requires for persisted
 * jobs, so the scheduling silently failed and no background check
 * ever ran (this was also the root cause of the original crash-loop
 * report: in 2.12.0 the same exception was uncaught). New EFTNative
 * JavascriptInterface lets the web UI show the real status
 * (permission / job / last poll) and offers a test notification and a
 * shortcut to the system notification settings.
 *
 * v2.12.2: crash fix — the background poll job (v2.12.0+) read the
 * WebView session cookie from its worker thread, which could throw an
 * Error on some devices and kill the whole app process; because the
 * job is persisted, Android re-delivered it the moment the app was
 * opened, so the app would close immediately and could not be opened
 * again (reinstall does not clear the job). The cookie is now read on
 * the main thread and the job catches Throwable everywhere (see
 * PollJobService). Also: CrashLog records any uncaught exception and
 * the app shows it on the next launch with a Copy button.
 */
public class MainActivity extends Activity {

    private static final int REQ_CAMERA = 100;
    private static final int REQ_NOTIF = 102;
    private static final int JOB_ID = 1;
    private static final String PREFS = "eft";
    private static final String KEY_URL = "server_url";
    private static final String APP_VERSION = "2.12.6";
    // Custom deep-link scheme: an OIDC flow that somehow ends up in the
    // browser redirects back into the app via win.strommingflix.eft://…
    private static final String DL_SCHEME = "win.strommingflix.eft";

    private WebView web;
    private PermissionRequest pendingPerm;
    private String serverUrl;
    /** Session cookie, captured on the main thread for use by the
     *  bridge/background threads (CookieManager is not thread-safe to
     *  call from workers — that bug crashed the app in 2.12.0/2.12.1). */
    private static volatile String sessionCookie = null;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        CrashLog.install(this);   // record crashes for the report dialog
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
        maybeShowCrashReport();
    }

    /**
     * v2.12.2: if the app (or its background job) crashed since the last
     * launch, show the stack trace with a Copy button so it can be
     * reported without USB debugging.
     */
    private void maybeShowCrashReport() {
        final String crash = CrashLog.get(this);
        if (crash == null) return;
        AlertDialog.Builder b = new AlertDialog.Builder(this);
        b.setTitle("The app crashed last time");
        b.setMessage(crash);
        b.setPositiveButton("Copy report", (d, w) -> {
            try {
                ClipboardManager cm = getSystemService(ClipboardManager.class);
                cm.setPrimaryClip(ClipData.newPlainText("EFT crash report", crash));
                Toast.makeText(this, "Crash report copied — you can now " +
                        "paste it into a bug report.", Toast.LENGTH_LONG).show();
            } catch (Throwable ignored) { }
        });
        b.setNeutralButton("Dismiss", (d, w) -> CrashLog.clear(this));
        b.setOnCancelListener(d -> CrashLog.clear(this));
        b.show();
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
        s.setUserAgentString(s.getUserAgentString() + " EFT-Android/2.12.6");

        // v2.12.3: bridge for the web UI's native-notification controls
        web.addJavascriptInterface(new NativeBridge(), "EFTNative");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                captureCookie();
            }
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
        // v2.12.1: the web UI points update links at /app.apk — handle
        // the download here (a WebView without a DownloadListener would
        // just do nothing). Hand it to the system DownloadManager: no
        // permissions needed, the system shows progress and, for APKs,
        // tapping the completed notification opens the package installer.
        web.setDownloadListener((url, userAgent, contentDisposition,
                                 mimeType, contentLength) -> {
            try {
                DownloadManager.Request req =
                        new DownloadManager.Request(Uri.parse(url));
                req.setMimeType(mimeType != null ? mimeType
                        : "application/vnd.android.package-archive");
                req.setTitle("Food Tracker update");
                req.setDescription("App update");
                req.setNotificationVisibility(
                        DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                String cookies = CookieManager.getInstance().getCookie(url);
                if (cookies != null) req.addRequestHeader("Cookie", cookies);
                DownloadManager dm = (DownloadManager)
                        getSystemService(DOWNLOAD_SERVICE);
                dm.enqueue(req);
                Toast.makeText(MainActivity.this,
                        "Downloading — tap the notification when it " +
                        "finishes to install.", Toast.LENGTH_LONG).show();
            } catch (Exception e) {
                // If the system download manager refuses (unknown
                // reasons), fall back to the browser.
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                } catch (Exception ignored) { }
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
        captureCookie();
        setContentView(web, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        try {
            enableNativeNotifications();
        } catch (Throwable t) {
            CrashLog.store(this, t);   // scheduling must never kill startup
            Toast.makeText(this, "Could not schedule background checks: " + t,
                    Toast.LENGTH_LONG).show();
        }
    }

    /** Refresh the cached session cookie (main thread only). */
    private void captureCookie() {
        try {
            if (serverUrl != null)
                sessionCookie = CookieManager.getInstance().getCookie(serverUrl);
        } catch (Throwable ignored) { }
    }

    /**
     * v2.12.4: download the update APK ourselves (the system
     * DownloadManager silently failed on a real device) and open the
     * package installer on it. Runs on a worker thread; toasts and the
     * installer are posted to the main thread. The outcome is stored in
     * the prefs ("last_update_dl") and shown by the web UI.
     */
    private void downloadUpdateApk() {
        final String base = serverUrl, cookie = sessionCookie;
        final android.os.Handler ui =
                new android.os.Handler(android.os.Looper.getMainLooper());
        ui.post(() -> Toast.makeText(this,
                "Downloading update…", Toast.LENGTH_SHORT).show());
        new Thread(() -> {
            String result;
            try {
                java.io.File dir = getExternalFilesDir("update");
                if (dir == null) dir = getFilesDir();
                //noinspection ResultOfMethodCallIgnored
                dir.mkdirs();
                final java.io.File out = new java.io.File(dir, "eft-update.apk");
                java.net.HttpURLConnection c = (java.net.HttpURLConnection)
                        new java.net.URL(base + "/app.apk").openConnection();
                if (cookie != null && !cookie.isEmpty())
                    c.setRequestProperty("Cookie", cookie);
                c.setConnectTimeout(15000);
                c.setReadTimeout(60000);
                int code = c.getResponseCode();
                if (code != 200) {
                    result = "HTTP " + code;
                } else {
                    java.io.InputStream in = c.getInputStream();
                    java.io.FileOutputStream fos = new java.io.FileOutputStream(out);
                    try {
                        byte[] buf = new byte[16384];
                        int n;
                        while ((n = in.read(buf)) > 0) fos.write(buf, 0, n);
                    } finally {
                        try { in.close(); } catch (Throwable ignored) { }
                        try { fos.close(); } catch (Throwable ignored) { }
                    }
                    result = "ok (" + out.length() + " bytes)";
                }
                c.disconnect();
            } catch (Throwable t) {
                CrashLog.store(this, t);
                result = "error: " + t;
            }
            final String r = result;
            final boolean ok = r.startsWith("ok");
            getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                    .putString("last_update_dl", r).apply();
            ui.post(() -> {
                Toast.makeText(this, ok
                        ? "Update downloaded — opening the installer…"
                        : "Update download failed: " + r,
                        Toast.LENGTH_LONG).show();
                if (!ok) return;
                try {
                    android.content.Intent it = new android.content.Intent(
                            android.content.Intent.ACTION_VIEW,
                            android.net.Uri.parse(
                                    "content://" + APKProvider.AUTHORITY + "/update.apk"));
                    it.setDataAndType(it.getData(),
                            "application/vnd.android.package-archive");
                    it.addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    startActivity(it);
                } catch (Throwable t2) {
                    CrashLog.store(this, t2);
                    Toast.makeText(this,
                            "Could not open the installer: " + t2,
                            Toast.LENGTH_LONG).show();
                }
            });
        }).start();
    }

    /**
     * v2.12.0: native notifications. Ask for the notification permission
     * (Android 13+) and schedule the periodic background check that polls
     * /api/push/inbox and raises system notifications. The job is persisted,
     * so it survives reboots without a boot receiver.
     */
    private void enableNativeNotifications() {
        if (Build.VERSION.SDK_INT >= 33) {
            String p = "android.permission.POST_NOTIFICATIONS";
            if (checkSelfPermission(p) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{p}, REQ_NOTIF);
            }
        }
        JobScheduler js = getSystemService(JobScheduler.class);
        JobInfo ji = new JobInfo.Builder(JOB_ID,
                new ComponentName(this, PollJobService.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPeriodic(30 * 60 * 1000L)   // ~every 30 minutes
                .setPersisted(true)              // survives reboots
                .build();
        js.schedule(ji);
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

    /**
     * v2.12.3: methods exposed to the web page as window.EFTNative.* —
     * used by Settings -> Notifications to show the real native state,
     * raise a test notification and jump to the system settings.
     */
    private class NativeBridge {

        /** "granted|scheduled|lastPollMillis|lastPollResult|crashed" */
        @JavascriptInterface
        public String status() {
            boolean granted = true;
            if (Build.VERSION.SDK_INT >= 33) {
                granted = checkSelfPermission("android.permission.POST_NOTIFICATIONS")
                        == PackageManager.PERMISSION_GRANTED;
            }
            boolean scheduled = false;
            try {
                scheduled = getSystemService(JobScheduler.class).getPendingJob(JOB_ID) != null;
            } catch (Throwable t) { scheduled = false; }
            SharedPreferences p = getSharedPreferences(PREFS, MODE_PRIVATE);
            boolean crashed = CrashLog.get(MainActivity.this) != null;
            return granted + "|" + scheduled + "|" + p.getLong("last_poll", 0)
                    + "|" + p.getString("last_poll_result", "never") + "|" + crashed
                    + "|" + p.getString("last_update_dl", "none");
        }

        @JavascriptInterface
        public void test() {
            // v2.12.6: bridge methods run on a non-Looper thread; posting
            // to the main thread is safe for notifications and lets us
            // show a toast so the result is never silent.
            new android.os.Handler(Looper.getMainLooper()).post(new Runnable() {
                @Override public void run() {
                    try {
                        PollJobService.notify(MainActivity.this,
                                "Test notification — native alerts are working ✓ " +
                                "(background checks run about every 30 minutes).");
                        Toast.makeText(MainActivity.this,
                                "Test notification sent — check the notification shade",
                                Toast.LENGTH_LONG).show();
                    } catch (Throwable t) {
                        CrashLog.store(MainActivity.this, t);
                        Toast.makeText(MainActivity.this,
                                "Test notification FAILED: " + t,
                                Toast.LENGTH_LONG).show();
                    }
                }
            });
        }

        /**
         * v2.12.6: run one poll right now (called by the web UI when the
         * app opens, so the status line refreshes immediately instead of
         * showing a stale "HTTP 401" from a poll that ran while logged
         * out).
         */
        @JavascriptInterface
        public void pollNow() {
            new android.os.Handler(Looper.getMainLooper()).post(new Runnable() {
                @Override public void run() {
                    try {
                        PollJobService.pollNow(MainActivity.this);
                        Toast.makeText(MainActivity.this,
                                "Checking now…", Toast.LENGTH_SHORT).show();
                    } catch (Throwable t) {
                        CrashLog.store(MainActivity.this, t);
                        Toast.makeText(MainActivity.this,
                                "Check failed: " + t, Toast.LENGTH_LONG).show();
                    }
                }
            });
        }

        @JavascriptInterface
        public void downloadUpdate() {
            try {
                downloadUpdateApk();
            } catch (Throwable t) {
                CrashLog.store(MainActivity.this, t);
            }
        }

        @JavascriptInterface
        public void openSettings() {
            try {
                Intent i = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                        .putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName());
                startActivity(i);
            } catch (Throwable t) {
                CrashLog.store(MainActivity.this, t);
                try {
                    // fallback: the app's details page still has
                    // the notification toggle on every Android version
                    startActivity(new Intent(
                            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                            Uri.fromParts("package", getPackageName(), null)));
                } catch (Throwable ignored) { }
            }
        }

        /**
         * v2.12.5: open a URL outside the WebView (real browser). The
         * intent:// anchor-click trick did nothing on the affected
         * device; going through native code makes failures visible.
         */
        @JavascriptInterface
        public void openUrl(String url) {
            try {
                Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url))
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(i);
                Toast.makeText(MainActivity.this,
                        "Opened in browser", Toast.LENGTH_SHORT).show();
            } catch (Throwable t) {
                CrashLog.store(MainActivity.this, t);
                Toast.makeText(MainActivity.this,
                        "Could not open the browser: " + t,
                        Toast.LENGTH_LONG).show();
            }
        }
    }
}
