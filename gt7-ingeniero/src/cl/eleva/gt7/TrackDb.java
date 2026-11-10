package cl.eleva.gt7;

import java.util.ArrayList;
import java.util.Locale;

/**
 * Circuitos que la app ya conoce. GT7 no dice en qué pista estás, pero las coordenadas de un
 * mismo circuito son siempre las mismas: después de la primera vuelta se compara la forma con
 * las pistas guardadas y, si coincide, se usan las mismas curvas (misma numeración) y nombre.
 */
final class TrackDb {
    static final int PTS = 64;

    static final class Track {
        int id;
        String name = "";
        float length;
        float[] x = new float[PTS], z = new float[PTS];
        float[] cs = new float[0], ce = new float[0];
        // circuitos de la base GT7 (vienen con la app)
        boolean builtin;
        int turns;                       // curvas oficiales
        float[] px, pz;                  // trazado, BPTS puntos por distancia
        float[] ax = new float[0], az = new float[0];   // vértices oficiales (si están)
        String label() { return name.length() > 0 ? name : "circuito " + id; }
    }

    static final int BPTS = 128;
    final ArrayList<Track> builtin = new ArrayList<Track>();

    /** Carga la base de circuitos de GT7 (res/raw/pistas_gt7.txt). */
    void loadBuiltin(String text) {
        builtin.clear();
        if (text == null) return;
        int id = 1000;
        for (String line : text.split("\n")) {
            if (line.startsWith("#") || line.trim().length() == 0) continue;
            try {
                String[] f = line.split("\\|", -1);
                Track t = new Track();
                t.builtin = true; t.id = id++;
                t.name = f[0]; t.turns = Integer.parseInt(f[1]); t.length = Float.parseFloat(f[2]);
                String[] pts = f[3].split(";");
                t.px = new float[pts.length]; t.pz = new float[pts.length];
                for (int k = 0; k < pts.length; k++) { String[] xy = pts[k].split(","); t.px[k] = Float.parseFloat(xy[0]); t.pz[k] = Float.parseFloat(xy[1]); }
                if (f.length > 4 && f[4].trim().length() > 0) {
                    String[] ap = f[4].trim().split(";");
                    t.ax = new float[ap.length]; t.az = new float[ap.length];
                    for (int k = 0; k < ap.length; k++) { String[] xy = ap[k].split(","); t.ax[k] = Float.parseFloat(xy[0]); t.az[k] = Float.parseFloat(xy[1]); }
                }
                if (t.px.length == BPTS) builtin.add(t);
            } catch (Exception ignored) { }
        }
    }

    /** Forma de una vuelta con n puntos repartidos por distancia. */
    static float[][] shape(Coach.Trace r, int n) {
        float len = r.d[r.n - 1];
        float[] x = new float[n], z = new float[n];
        int j = 0;
        for (int k = 0; k < n; k++) {
            float d = len * k / n;
            while (j < r.n - 1 && r.d[j] < d) j++;
            x[k] = r.x[j]; z[k] = r.z[j];
        }
        return new float[][]{x, z};
    }

    float lastErr;

    static float segDist(float x, float z, float ax, float az, float bx, float bz) {
        float dx = bx - ax, dz = bz - az, l2 = dx * dx + dz * dz;
        float f = l2 > 0 ? ((x - ax) * dx + (z - az) * dz) / l2 : 0;
        f = Math.max(0, Math.min(1, f));
        return (float) Math.hypot(x - (ax + f * dx), z - (az + f * dz));
    }

    /**
     * Busca la vuelta en la base GT7: largo parecido (±8 %) y misma forma en el mismo sentido,
     * probando todos los puntos de partida (el trazado guardado no empieza necesariamente en la meta).
     */
    Track matchBuiltin(Coach.Trace r) {
        float len = r.d[r.n - 1];
        float[][] sh = shape(r, BPTS);
        Track best = null;
        float bestErr = 35f;
        for (Track t : builtin) {
            if (Math.abs(t.length - len) > 0.08f * Math.max(len, t.length)) continue;
            for (int s = 0; s < BPTS; s++) {
                float err = 0, lim = bestErr * BPTS;
                int k = 0;
                for (; k < BPTS && err < lim; k++) {
                    float m = Float.MAX_VALUE;
                    for (int o = -2; o <= 1; o++) {   // distancia al tramo más cercano (sin error de muestreo)
                        int q = ((k + s + o) % BPTS + BPTS) % BPTS, q2 = (q + 1) % BPTS;
                        m = Math.min(m, segDist(sh[0][k], sh[1][k], t.px[q], t.pz[q], t.px[q2], t.pz[q2]));
                    }
                    err += m;
                }
                if (k == BPTS && err / BPTS < bestErr) { bestErr = err / BPTS; best = t; }
            }
        }
        lastErr = bestErr;
        return best;
    }

    final ArrayList<Track> tracks = new ArrayList<Track>();

    /** Forma de una vuelta: PTS puntos repartidos por distancia. */
    static float[][] shape(Coach.Trace r) {
        float len = r.d[r.n - 1];
        float[] x = new float[PTS], z = new float[PTS];
        int j = 0;
        for (int k = 0; k < PTS; k++) {
            float d = len * k / PTS;
            while (j < r.n - 1 && r.d[j] < d) j++;
            x[k] = r.x[j]; z[k] = r.z[j];
        }
        return new float[][]{x, z};
    }

    /** Busca el circuito: largo parecido (±4 %) y forma a menos de 25 m en promedio. */
    Track match(Coach.Trace r) {
        Track b = matchBuiltin(r);
        if (b != null) return b;
        float len = r.d[r.n - 1];
        float[][] sh = shape(r);
        Track best = null;
        float bestErr = 25f;
        for (Track t : tracks) {
            if (Math.abs(t.length - len) > 0.04f * Math.max(len, t.length)) continue;
            float err = 0;
            for (int k = 0; k < PTS; k++) err += (float) Math.hypot(t.x[k] - sh[0][k], t.z[k] - sh[1][k]);
            err /= PTS;
            if (err < bestErr) { bestErr = err; best = t; }
        }
        return best;
    }

    Track add(Coach.Trace r, float[] cs, float[] ce) {
        Track t = new Track();
        int id = 1;
        for (Track o : tracks) id = Math.max(id, o.id + 1);
        t.id = id;
        t.length = r.d[r.n - 1];
        float[][] sh = shape(r);
        t.x = sh[0]; t.z = sh[1]; t.cs = cs; t.ce = ce;
        tracks.add(t);
        return t;
    }

    // ---- guardar / cargar (texto simple, una pista por línea) ----
    String serialize() {
        StringBuilder sb = new StringBuilder();
        for (Track t : tracks) {
            sb.append(t.id).append('|').append(t.name.replace('|', ' ').replace('\n', ' ')).append('|')
              .append(String.format(Locale.US, "%.1f", t.length)).append('|');
            for (int k = 0; k < PTS; k++) sb.append(k > 0 ? ";" : "").append(String.format(Locale.US, "%.1f,%.1f", t.x[k], t.z[k]));
            sb.append('|');
            for (int c = 0; c < t.cs.length; c++) sb.append(c > 0 ? ";" : "").append(String.format(Locale.US, "%.5f,%.5f", t.cs[c], t.ce[c]));
            sb.append('\n');
        }
        return sb.toString();
    }

    void load(String text) {
        tracks.clear();
        if (text == null) return;
        for (String line : text.split("\n")) {
            try {
                String[] f = line.split("\\|", -1);
                if (f.length < 5) continue;
                Track t = new Track();
                t.id = Integer.parseInt(f[0].trim());
                t.name = f[1];
                t.length = Float.parseFloat(f[2]);
                String[] pts = f[3].split(";");
                if (pts.length != PTS) continue;
                for (int k = 0; k < PTS; k++) { String[] xy = pts[k].split(","); t.x[k] = Float.parseFloat(xy[0]); t.z[k] = Float.parseFloat(xy[1]); }
                String[] cs = f[4].length() == 0 ? new String[0] : f[4].split(";");
                t.cs = new float[cs.length]; t.ce = new float[cs.length];
                for (int c = 0; c < cs.length; c++) { String[] se = cs[c].split(","); t.cs[c] = Float.parseFloat(se[0]); t.ce[c] = Float.parseFloat(se[1]); }
                tracks.add(t);
            } catch (Exception ignored) { }
        }
    }

    Track byId(int id) { for (Track t : tracks) if (t.id == id) return t; return null; }
}
