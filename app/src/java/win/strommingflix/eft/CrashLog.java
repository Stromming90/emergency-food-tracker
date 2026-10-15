package win.strommingflix.eft;

import android.content.Context;
import android.content.SharedPreferences;

import java.io.PrintWriter;
import java.io.StringWriter;
import java.util.Date;

/**
 * v2.12.2: tiny crash recorder. Uncaught exceptions (in the activity or
 * the background poll job) are written to the app's shared prefs, and
 * MainActivity shows them on the next launch with a Copy button — so a
 * crash on a phone without USB debugging can still be reported.
 *
 * The previous uncaught-exception handler is chained to, so the system
 * crash dialog / process death behaviour is unchanged.
 */
public final class CrashLog {

    private static final String KEY = "last_crash";

    private CrashLog() { }

    /** Capture every uncaught exception in this process. */
    public static void install(final Context ctx) {
        final Thread.UncaughtExceptionHandler prev =
                Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((t, e) -> {
            store(ctx, e);
            if (prev != null) prev.uncaughtException(t, e);
        });
    }

    /** Record a caught-but-serious throwable (never rethrown). */
    public static void store(Context ctx, Throwable t) {
        try {
            StringWriter sw = new StringWriter();
            sw.write(new Date().toString());
            sw.write(" (app v2.12.6, Android ");
            sw.write(android.os.Build.VERSION.RELEASE);
            sw.write(")\n");
            t.printStackTrace(new PrintWriter(sw));
            prefs(ctx).edit().putString(KEY, sw.toString()).apply();
        } catch (Throwable ignored) { }
    }

    public static String get(Context ctx) {
        return prefs(ctx).getString(KEY, null);
    }

    public static void clear(Context ctx) {
        prefs(ctx).edit().remove(KEY).apply();
    }

    private static SharedPreferences prefs(Context ctx) {
        return ctx.getSharedPreferences("eft", Context.MODE_PRIVATE);
    }
}
