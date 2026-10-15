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
 */
public class PollJobService extends JobService {

    private Thread worker;

    @Override
    public boolean onStartJob(final JobParameters params) {
        worker = new Thread(() -> {
            try {
                poll();
            } catch (Exception ignored) {
            }
            jobFinished(params, false);
        });
        worker.start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        if (worker != null) worker.interrupt();
        return false;   // no retry; the next periodic run comes anyway
    }

    private void poll() {
        SharedPreferences prefs = getSharedPreferences("eft", MODE_PRIVATE);
        String base = prefs.getString("server_url", null);
        if (base == null || base.isEmpty()) return;   // app not set up yet
        String device = prefs.getString("device_id", null);
        if (device == null) {
            device = UUID.randomUUID().toString();
            prefs.edit().putString("device_id", device).apply();
        }
        // The WebView session cookie lives in the same process's
        // CookieManager; without it we are not logged in (yet).
        String cookie = CookieManager.getInstance().getCookie(base);
        if (cookie == null || cookie.isEmpty()) return;

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
                if (i > 0) body.append("\\n");
                body.append(alerts.getString(i));
            }
            if (more > 0) body.append("\\n… and ").append(more).append(" more");
            raiseNotification(body.toString());
        } catch (Exception ignored) {
        } finally {
            if (c != null) c.disconnect();
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
