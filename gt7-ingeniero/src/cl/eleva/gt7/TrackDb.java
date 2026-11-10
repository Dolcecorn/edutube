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
        String label() { return name.length() > 0 ? name : "circuito " + id; }
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
