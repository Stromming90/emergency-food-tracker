package win.strommingflix.eft;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileNotFoundException;

/**
 * v2.12.4: serves the downloaded update APK to the system package
 * installer through a content:// URI — the installer cannot open raw
 * app file paths, and this replaces the system DownloadManager path
 * that silently failed on a real device. The file is written by
 * MainActivity.downloadUpdateApk() into getExternalFilesDir("update").
 */
public class APKProvider extends ContentProvider {

    public static final String AUTHORITY = "win.strommingflix.eft.apk";

    @Override
    public boolean onCreate() {
        return true;
    }

    private File file() {
        File dir = getContext().getExternalFilesDir("update");
        if (dir == null) dir = getContext().getFilesDir();
        return new File(dir, "eft-update.apk");
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode)
            throws FileNotFoundException {
        File f = file();
        if (!f.exists()) throw new FileNotFoundException("no update downloaded");
        return ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection,
                        String[] selectionArgs, String sortOrder) {
        // The package installer asks for the display name and size.
        if (projection == null) {
            projection = new String[]{OpenableColumns.DISPLAY_NAME,
                    OpenableColumns.SIZE};
        }
        File f = file();
        Object[] row = new Object[projection.length];
        for (int i = 0; i < projection.length; i++) {
            if (OpenableColumns.DISPLAY_NAME.equals(projection[i])) {
                row[i] = "emergency-food-tracker-update.apk";
            } else if (OpenableColumns.SIZE.equals(projection[i])) {
                row[i] = f.exists() ? f.length() : 0;
            } else {
                row[i] = null;
            }
        }
        MatrixCursor c = new MatrixCursor(projection);
        c.addRow(row);
        return c;
    }

    @Override
    public String getType(Uri uri) {
        return "application/vnd.android.package-archive";
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection,
                      String[] selectionArgs) {
        return 0;
    }
}
