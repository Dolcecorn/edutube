package cl.eleva.gt7;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Random;

/** Prueba el reconocimiento de circuitos: vueltas sintéticas sobre los trazados de GT7. */
public class TrackTest {
    public static void main(String[] a) throws Exception {
        TrackDb db = new TrackDb();
        db.loadBuiltin(new String(Files.readAllBytes(Paths.get(a[0])), "UTF-8"));
        System.out.println("pistas en la base: " + db.builtin.size());
        Random rnd = new Random(3);
        int ok = 0, n = 0, exact = 0;
        for (String line : new String(Files.readAllBytes(Paths.get(a[1])), "UTF-8").split("\n")) {
            String[] f = line.split("\\|");
            String[] pts = f[1].split(";");
            int m = pts.length;
            float[] x = new float[m], z = new float[m];
            for (int i = 0; i < m; i++) { String[] xy = pts[i].split(","); x[i] = Float.parseFloat(xy[0]); z[i] = Float.parseFloat(xy[1]); }
            int off = rnd.nextInt(m);           // la vuelta parte en otro punto
            Coach.Trace tr = new Coach.Trace();
            float d = 0, px = 0, pz = 0;
            float nx = (rnd.nextFloat() - 0.5f) * 6, nz = (rnd.nextFloat() - 0.5f) * 6;
            for (int i = 0; i < m - 1; i++) {
                int i0 = (i + off) % m, i1 = (i + off + 1) % m;
                for (int s = 0; s < 10; s++) {
                    float fr = s / 10f;
                    float qx = x[i0] + (x[i1] - x[i0]) * fr + nx, qz = z[i0] + (z[i1] - z[i0]) * fr + nz;
                    if (tr.n > 0) d += (float) Math.hypot(qx - px, qz - pz);
                    tr.add(qx, qz, d, d / 40f, 150, 255, 0, 4);
                    px = qx; pz = qz;
                }
                if (rnd.nextInt(40) == 0) { nx = (rnd.nextFloat() - 0.5f) * 6; nz = (rnd.nextFloat() - 0.5f) * 6; }
            }
            // velocidad según curvatura (para el vértice)
            for (int i = 5; i < tr.n - 5; i++) {
                double h0 = Math.atan2(tr.z[i] - tr.z[i - 5], tr.x[i] - tr.x[i - 5]), h1 = Math.atan2(tr.z[i + 5] - tr.z[i], tr.x[i + 5] - tr.x[i]);
                double dh = Math.abs(h1 - h0); if (dh > Math.PI) dh = 2 * Math.PI - dh;
                double k = dh / Math.max(1, tr.d[i + 5] - tr.d[i - 5]);
                tr.v[i] = (float) Math.min(280, 3.6 * Math.sqrt(12 / Math.max(1e-4, k)));
            }
            n++;
            long t0 = System.nanoTime();
            TrackDb.Track t = db.matchBuiltin(tr);
            long ms = (System.nanoTime() - t0) / 1000000;
            boolean good = t != null && t.name.equals(f[0]);
            if (good) ok++;
            String det = "";
            if (t != null) {
                Coach c = new Coach();
                c.ref = tr;
                c.useTrack(t.ax, t.az, t.turns);
                det = " curvas " + c.nc + "/" + t.turns + (t.ax.length > 0 ? " (vértices)" : "");
                if (c.nc == t.turns) exact++;
            }
            System.out.println((good ? "OK   " : "MAL  ") + f[0] + " -> " + (t != null ? t.name : "-")
                    + String.format(" err %.1f m, %d ms", db.lastErr, ms) + det);
        }
        System.out.println("reconocidas " + ok + "/" + n + ", curvas exactas " + exact);
    }
}
