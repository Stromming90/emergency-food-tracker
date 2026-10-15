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
                poll(fBase, fDevice, fCookie);
            } catch (Throwable t) {
                CrashLog.store(PollJobService.this, t);
            } finally {
                try { jobFinished(params, false); } catch (Throwable ignored) { }
            }
        });
        worker.start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        try {
            if (worker != null) worker.interrupt();
        } catch (Throwable ignored) { }
        return false;   // no retry; the next periodic run comes anyway
    }

    private void poll(String base, String device, String cookie) {
        HttpURLConnection c = null;
        try {
            URL u = new URL(base + "/api/push/inbox?device=" + device);
            c = (HttpURLConnection) u.openConnection();
            c.setRequestProperty("Cookie", cookie);
            c.setConnectTimeout(15000);
            c.setReadTimeout(15000);
            if (c.getResponseCode() != 200) return;   // not logged in / server down
            InputStream in = c.getInputStream();
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) bos.write(buf, 0, n);
            JSONObject o = new JSONObject(bos.toString("UTF-8"));
            JSONArray alerts = o.optJSONArray("alerts");
            int more = o.optInt("more", 0);
            if (alerts == null || alerts.length() == 0) return;
            StringBuilder body = new StringBuilder();
            for (int i = 0; i < alerts.length(); i++) {
                if (i > 0) body.append("\n");
                body.append(alerts.getString(i));
            }
            if (more > 0) body.append("\n… and ").append(more).append(" more");
            raiseNotification(body.toString());
        } catch (Throwable t) {
            CrashLog.store(this, t);
        } finally {
            if (c != null) {
                try { c.disconnect(); } catch (Throwable ignored) { }
            }
        }
    }

    private void raiseNotification(String body) {
        NotificationManager nm =
                (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm == null) return;
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(
                    "alerts", "Food storage alerts",
                    NotificationManager.IMPORTANCE_DEFAULT);
            ch.setDescription("Expiring food alerts from the tracker server");
            nm.createNotificationChannel(ch);
        }
        PendingIntent pi = PendingIntent.getActivity(this, 0,
                new Intent(this, MainActivity.class),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, "alerts")
                : new Notification.Builder(this);
        b.setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle("Food storage alert")
                .setContentText(body)
                .setStyle(new Notification.BigTextStyle().bigText(body))
                .setContentIntent(pi)
                .setAutoCancel(true);
        nm.notify(1, b.build());
    }
}
