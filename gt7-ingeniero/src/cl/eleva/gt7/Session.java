package cl.eleva.gt7;

import java.util.ArrayList;
import java.util.Locale;

/** Historial de la carrera: vueltas, curvas y eventos, para el análisis y el resumen final. */
final class Session {
    static final int MAXC = 64;

    static final class Lap {
        int lap, ms;
        float maxKmh, fuelUsed = -1;
        int lock, spin, over, under;
    }

    static final class Event {
        int lap, corner, type, wheels;
        float kmh, x, z;
        Event(int lap, int corner, int type, int wheels, float kmh, float x, float z) {
            this.lap = lap; this.corner = corner; this.type = type; this.wheels = wheels; this.kmh = kmh; this.x = x; this.z = z;
        }
    }

    final ArrayList<Lap> laps = new ArrayList<Lap>();
    final ArrayList<Event> events = new ArrayList<Event>();
    // por curva (índice 0 = curva 1)
    final float[] lossSum = new float[MAXC];
    final int[] lossN = new int[MAXC];
    final float[] bestMinV = new float[MAXC], lastMinV = new float[MAXC];
    final int[][] evByCorner = new int[4][MAXC];
    int corners;            // cantidad de curvas detectadas
    float topKmh;
    int carCode, totalLaps;
    long startedAt = System.currentTimeMillis();

    void clear() {
        laps.clear(); events.clear(); corners = 0; topKmh = 0;
        for (int i = 0; i < MAXC; i++) { lossSum[i] = 0; lossN[i] = 0; bestMinV[i] = 0; lastMinV[i] = 0; }
        for (int[] a : evByCorner) java.util.Arrays.fill(a, 0);
        startedAt = System.currentTimeMillis();
    }

    void addEvent(int lap, int corner, int type, int wheels, float kmh, float x, float z) {
        if (events.size() > 2000) events.remove(0);
        events.add(new Event(lap, corner, type, wheels, kmh, x, z));
        if (corner >= 0 && corner < MAXC) evByCorner[type][corner]++;
    }

    void cornerResult(int c, float loss, float minKmh) {
        if (c < 0 || c >= MAXC) return;
        lossSum[c] += loss; lossN[c]++;
        lastMinV[c] = minKmh;
        if (minKmh > bestMinV[c]) bestMinV[c] = minKmh;
        if (c + 1 > corners) corners = c + 1;
    }

    Lap addLap(int lap, int ms, float maxKmh, float fuelUsed) {
        Lap l = new Lap();
        l.lap = lap; l.ms = ms; l.maxKmh = maxKmh; l.fuelUsed = fuelUsed;
        for (Event e : events) if (e.lap == lap) {
            if (e.type == Dynamics.LOCK) l.lock++; else if (e.type == Dynamics.SPIN) l.spin++;
            else if (e.type == Dynamics.OVER) l.over++; else l.under++;
        }
        laps.add(l);
        if (maxKmh > topKmh) topKmh = maxKmh;
        return l;
    }

    Lap best() {
        Lap b = null;
        for (Lap l : laps) if (l.ms > 0 && (b == null || l.ms < b.ms)) b = l;
        return b;
    }

    float avgLoss(int c) { return lossN[c] > 0 ? lossSum[c] / lossN[c] : 0; }

    /** Curvas ordenadas por tiempo perdido promedio (de más a menos). */
    int[] worstCorners(int n) {
        int[] idx = new int[Math.min(n, corners)];
        boolean[] used = new boolean[corners];
        for (int k = 0; k < idx.length; k++) {
            int w = -1;
            for (int c = 0; c < corners; c++) if (!used[c] && lossN[c] > 0 && (w < 0 || avgLoss(c) > avgLoss(w))) w = c;
            if (w < 0 || avgLoss(w) < 0.05f) { int[] r = new int[k]; System.arraycopy(idx, 0, r, 0, k); return r; }
            used[w] = true; idx[k] = w;
        }
        return idx;
    }

    int count(int type) { int n = 0; for (Event e : events) if (e.type == type) n++; return n; }

    int worstCornerFor(int type) {
        int w = -1;
        for (int c = 0; c < MAXC; c++) if (evByCorner[type][c] > 0 && (w < 0 || evByCorner[type][c] > evByCorner[type][w])) w = c;
        return w;
    }

    /** Desviación de los tiempos de vuelta (sin la 1ª), en segundos. */
    float consistency() {
        int n = 0; double s = 0, s2 = 0;
        for (Lap l : laps) if (l.lap > 1 && l.ms > 0) { n++; s += l.ms / 1000.0; s2 += (l.ms / 1000.0) * (l.ms / 1000.0); }
        if (n < 2) return -1;
        double m = s / n;
        return (float) Math.sqrt(Math.max(0, s2 / n - m * m));
    }

    /** Resumen hablado de fin de carrera: lo más importante para bajar el tiempo de vuelta. */
    String debrief() {
        StringBuilder sb = new StringBuilder("Resumen de la carrera. ");
        Lap b = best();
        if (b == null) return sb.append("No alcancé a registrar vueltas completas.").toString();
        sb.append("Tu mejor vuelta fue la ").append(b.lap).append(", ").append(Engineer.speakTime(b.ms)).append(". ");
        float cons = consistency();
        if (cons >= 0) sb.append(cons < 0.4f ? "Muy constante: tus vueltas variaron " : "Tus vueltas variaron ")
                .append(Engineer.speakDelta(cons)).append(" en promedio. ");
        int[] worst = worstCorners(3);
        if (worst.length > 0) {
            sb.append("Donde más tiempo pierdes: ");
            for (int k = 0; k < worst.length; k++) {
                int c = worst[k];
                sb.append(k == 0 ? "" : k == worst.length - 1 ? " y " : ", ").append("curva ").append(c + 1)
                  .append(", ").append(Engineer.speakDelta(avgLoss(c))).append(" por vuelta");
            }
            sb.append(". ");
        }
        appendType(sb, Dynamics.LOCK, "Bloqueaste ruedas", "frena un poco menos fuerte al inicio o suelta antes el freno");
        appendType(sb, Dynamics.SPIN, "Patinaste", "dosifica el acelerador a la salida");
        appendType(sb, Dynamics.OVER, "Se te fue la cola", "acelera más suave en el vértice");
        appendType(sb, Dynamics.UNDER, "El auto no dobló", "entra más lento y suelta el freno de a poco");
        if (topKmh > 0) sb.append("Velocidad máxima ").append(Math.round(topKmh)).append(" kilómetros por hora. ");
        if (worst.length > 0) {
            int c = worst[0];
            float dv = bestMinV[c] - lastMinV[c];
            sb.append("Para la próxima: concéntrate en la curva ").append(c + 1);
            if (dv > 3) sb.append(", en tu mejor paso llevaste ").append(Math.round(dv)).append(" kilómetros por hora más en el vértice");
            sb.append(".");
        }
        return sb.toString().trim();
    }

    private void appendType(StringBuilder sb, int type, String what, String fix) {
        int n = count(type);
        if (n == 0) return;
        int c = worstCornerFor(type);
        sb.append(what).append(' ').append(n).append(n == 1 ? " vez" : " veces");
        if (c >= 0) sb.append(", sobre todo en la curva ").append(c + 1);
        sb.append(": ").append(fix).append(". ");
    }

    String csv() {
        StringBuilder sb = new StringBuilder("vuelta,tiempo,tiempo_ms,vel_max_kmh,combustible_pct,bloqueos,patinajes,sobreviraje,subviraje\n");
        for (Lap l : laps)
            sb.append(l.lap).append(',').append(Engineer.msText(l.ms)).append(',').append(l.ms).append(',')
              .append(Math.round(l.maxKmh)).append(',').append(l.fuelUsed >= 0 ? String.format(Locale.US, "%.2f", l.fuelUsed) : "")
              .append(',').append(l.lock).append(',').append(l.spin).append(',').append(l.over).append(',').append(l.under).append('\n');
        sb.append("\ncurva,perdida_media_s,vel_min_mejor,vel_min_ultima,bloqueos,patinajes,sobreviraje,subviraje\n");
        for (int c = 0; c < corners; c++)
            sb.append(c + 1).append(',').append(String.format(Locale.US, "%.2f", avgLoss(c))).append(',')
              .append(Math.round(bestMinV[c])).append(',').append(Math.round(lastMinV[c])).append(',')
              .append(evByCorner[0][c]).append(',').append(evByCorner[1][c]).append(',')
              .append(evByCorner[2][c]).append(',').append(evByCorner[3][c]).append('\n');
        return sb.toString();
    }
}
