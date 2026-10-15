package win.strommingflix.eft;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.job.JobParameters;
import android.app.job.JobService;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.webkit.CookieManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.UUID;

/**
 * v2.12.0: background check for native notifications.
 *
 * Scheduled by MainActivity roughly every 30 minutes (persisted across
 * reboots). Polls GET /api/push/inbox?device=<uuid> with the WebView's
 * session cookie and raises a system notification when items worsened.
 * The first poll only sets the baseline on the server, so a fresh
 * install stays quiet until something actually changes. Each
 * successful poll refreshes the login session server-side, so the app
 * keeps working in the background without re-login.
 *
 * v2.12.6: a poll can be run on demand. The web UI calls
 * EFTNative.pollNow() right after login, so the "Last check" status is
 * fresh immediately (a background 401 recorded while the user was
 * logged out used to linger for up to 30 minutes). The poll logic is
 * static (doPoll) and shared by the job and the bridge; the session
 * cookie is still read only on the main thread.
 *
 * v2.12.3: the notification code moved into a static notify() method
 * (shared with the in-app test button), and every poll records a
 * last_poll / last_poll_result pair in the shared prefs so the web UI
 * can show the real background status (see the EFTNative bridge in
 * MainActivity).
 *
 * v2.12.2 CRASH FIX: this service runs inside the app's main process,
 * so any exception that escapes it kills the whole app — and since the
 * job is persisted, Android re-delivers it the moment the app process
 * starts, which turned a single background crash into "the app closes
 * and can never open again" (a reinstall does not clear the persisted
 * job). Two changes fix that:
 *  - The session cookie is now read on the MAIN thread (inside
 *    onStartJob, which runs there). CookieManager/WebView access from
 *    the worker thread could throw an *Error* (e.g. native WebView
 *    provider load failure) which catch(Exception) cannot intercept.
 *  - Everything catches Throwable and records it via CrashLog, so the
 *    job can never take the process down again. The HTTP request still
 *    runs off the main thread (network-on-main would otherwise ANR).
 */
public class PollJobService extends JobService {

    private Thread worker;

    @Override
    public boolean onStartJob(final JobParameters params) {
        String base = null;
        String device = null;
        String cookie = null;
        try {
            SharedPreferences prefs = getSharedPreferences("eft", MODE_PRIVATE);
            base = prefs.getString("server_url", null);
            if (base == null || base.isEmpty()) return false; // not set up yet
            device = prefs.getString("device_id", null);
            if (device == null) {
                device = UUID.randomUUID().toString();
                prefs.edit().putString("device_id", device).apply();
            }
            // v2.12.2: main-thread cookie read (onStartJob has a Looper).
            cookie = CookieManager.getInstance().getCookie(base);
        } catch (Throwable t) {
            CrashLog.store(this, t);   // record, never crash the process
            return false;
        }
        if (cookie == null || cookie.isEmpty()) return false; // not logged in
        final String fBase = base, fDevice = device, fCookie = cookie;
        worker = new Thread(() -> {
            try {
                doPoll(this, fBase, fDevice, fCookie);
            } catch (Throwable t) {
                CrashLog.store(PollJobService.this, t);
            } finally {
                try { jobFinished(params, false); } catch (Throwable ignored) { }
            }
        });
        worker.start();
        return true;
    }

    /**
     * v2.12.6: run one poll right now. MUST be called from the main
     * thread (the cookie read requires it); the HTTP runs on a worker.
     */
    static void pollNow(final android.content.Context ctx) {
        try {
            android.content.SharedPreferences prefs =
                    ctx.getSharedPreferences("eft", android.content.Context.MODE_PRIVATE);
            String base = prefs.getString("server_url", null);
            if (base == null || base.isEmpty()) return;   // not set up
            String device = prefs.getString("device_id", null);
            if (device == null) {
                device = java.util.UUID.randomUUID().toString();
                prefs.edit().putString("device_id", device).apply();
            }
            String cookie = android.webkit.CookieManager.getInstance().getCookie(base);
            if (cookie == null || cookie.isEmpty()) {
                record(ctx, "no session cookie (not logged in)");
                return;
            }
            final String fBase = base, fDevice = device, fCookie = cookie;
            new Thread(() -> {
                try {
                    doPoll(ctx, fBase, fDevice, fCookie);
                } catch (Throwable t) {
                    CrashLog.store(ctx, t);
                }
            }).start();
        } catch (Throwable t) {
            CrashLog.store(ctx, t);
        }
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        try {
            if (worker != null) worker.interrupt();
        } catch (Throwable ignored) { }
        return false;   // no retry; the next periodic run comes anyway
    }

    static void record(android.content.Context ctx, String result) {
        try {
            ctx.getSharedPreferences("eft", android.content.Context.MODE_PRIVATE).edit()
                    .putLong("last_poll", System.currentTimeMillis())
                    .putString("last_poll_result", result).apply();
        } catch (Throwable ignored) { }
    }

    static void doPoll(final android.content.Context ctx, String base, String device, String cookie) {
        HttpURLConnection c = null;
        try {
            URL u = new URL(base + "/api/push/inbox?device=" + device);
            c = (HttpURLConnection) u.openConnection();
            c.setRequestProperty("Cookie", cookie);
            c.setConnectTimeout(15000);
            c.setReadTimeout(15000);
            int code = c.getResponseCode();
            if (code != 200) { record(ctx, "HTTP " + code); return; }
            InputStream in = c.getInputStream();
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) bos.write(buf, 0, n);
            JSONObject o = new JSONObject(bos.toString("UTF-8"));
            JSONArray alerts = o.optJSONArray("alerts");
            int more = o.optInt("more", 0);
            if (alerts == null || alerts.length() == 0) { record(ctx, "ok (no alerts)"); return; }
            StringBuilder body = new StringBuilder();
            for (int i = 0; i < alerts.length(); i++) {
                if (i > 0) body.append("\n");
                body.append(alerts.getString(i));
            }
            if (more > 0) body.append("\n… and ").append(more).append(" more");
            notify(ctx, body.toString());
            record(ctx, "ok (" + alerts.length() + " alert(s))");
        } catch (Throwable t) {
            CrashLog.store(ctx, t);
            record(ctx, "error: " + t);
        } finally {
            if (c != null) {
                try { c.disconnect(); } catch (Throwable ignored) { }
            }
        }
    }

    /** Raise (or test) the alert notification. Static: shared by the
     *  background poll and the in-app test button. */
    static void notify(android.content.Context ctx, String body) {
        NotificationManager nm =
                (NotificationManager) ctx.getSystemService(NOTIFICATION_SERVICE);
        if (nm == null) return;
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(
                    "alerts", "Food storage alerts",
                    NotificationManager.IMPORTANCE_DEFAULT);
            ch.setDescription("Expiring food alerts from the tracker server");
            nm.createNotificationChannel(ch);
        }
        PendingIntent pi = PendingIntent.getActivity(ctx, 0,
                new Intent(ctx, MainActivity.class),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(ctx, "alerts")
                : new Notification.Builder(ctx);
        b.setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle("Food storage alert")
                .setContentText(body)
                .setStyle(new Notification.BigTextStyle().bigText(body))
                .setContentIntent(pi)
                .setAutoCancel(true);
        nm.notify(1, b.build());
    }
}
