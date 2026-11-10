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
        int s1 = -1, s2 = -1, s3 = -1;   // tiempos de sector en ms (-1 = sin dato)
        boolean pit;                     // vuelta con paso por boxes
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
    String trackName = "";
    long startedAt = System.currentTimeMillis();

    void clear() {
        laps.clear(); events.clear(); corners = 0; topKmh = 0; trackName = "";
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
        for (Lap l : laps) if (l.lap > 1 && l.ms > 0 && !l.pit) { n++; s += l.ms / 1000.0; s2 += (l.ms / 1000.0) * (l.ms / 1000.0); }
        if (n < 2) return -1;
        double m = s / n;
        return (float) Math.sqrt(Math.max(0, s2 / n - m * m));
    }

    /** Mejor tiempo del sector k (0..2) en ms, -1 sin datos. */
    int bestSector(int k) {
        int b = -1;
        for (Lap l : laps) {
            int v = k == 0 ? l.s1 : k == 1 ? l.s2 : l.s3;
            if (v > 0 && (b < 0 || v < b)) b = v;
        }
        return b;
    }

    /** Vuelta ideal = suma de los mejores sectores; -1 sin datos de los 3. */
    int idealMs() {
        int a = bestSector(0), b = bestSector(1), c = bestSector(2);
        return a > 0 && b > 0 && c > 0 ? a + b + c : -1;
    }

    /** Sector (0..2) donde tu mejor vuelta está más lejos de tu mejor sector; -1 sin datos. */
    int weakSector() {
        Lap b = best();
        if (b == null || b.s1 <= 0 || b.s2 <= 0 || b.s3 <= 0) return -1;
        int[] v = {b.s1, b.s2, b.s3};
        int w = -1, wd = 50;   // menos de 5 centésimas no cuenta
        for (int k = 0; k < 3; k++) { int d = v[k] - bestSector(k); if (d > wd) { wd = d; w = k; } }
        return w;
    }

    /** Vueltas distintas (de las últimas n) en que hubo un evento del tipo en la curva c. */
    int lapsWith(int type, int c, int lastN) {
        int maxLap = 0;
        for (Event e : events) maxLap = Math.max(maxLap, e.lap);
        int seen = 0, n = 0;
        for (int lap = maxLap; lap > maxLap - lastN && lap > 0; lap--) {
            for (Event e : events) if (e.lap == lap && e.type == type && e.corner == c) { n++; break; }
            seen++;
        }
        return n;
    }

    /** Cantidad de vueltas distintas con eventos de este tipo en su peor curva (para hablar de tendencias). */
    int trendLaps(int type) {
        int c = worstCornerFor(type);
        if (c < 0) return 0;
        java.util.HashSet<Integer> l = new java.util.HashSet<Integer>();
        for (Event e : events) if (e.type == type && e.corner == c) l.add(e.lap);
        return l.size();
    }

    /** Resumen de fin de carrera en puntos: lo más importante para bajar el tiempo de vuelta. */
    ArrayList<String> debriefItems() {
        ArrayList<String> out = new ArrayList<String>();
        Lap b = best();
        if (b == null) { out.add("No alcancé a registrar vueltas completas."); return out; }
        out.add("Mejor vuelta: la " + b.lap + ", " + Engineer.speakTime(b.ms) + ".");
        int ideal = idealMs();
        if (ideal > 0 && ideal < b.ms) {
            String it = "Vuelta ideal con tus mejores sectores: " + Engineer.speakTime(ideal) + ", "
                    + Engineer.speakDelta((b.ms - ideal) / 1000f) + " menos que tu mejor.";
            int ws = weakSector();
            if (ws >= 0) it += " Lo que más falta está en el sector " + (ws + 1) + ".";
            out.add(it);
        }
        float cons = consistency();
        if (cons >= 0) out.add((cons < 0.4f ? "Muy constante: tus vueltas variaron " : "Constancia: tus vueltas variaron ")
                + Engineer.speakDelta(cons) + " en promedio.");
        int[] worst = worstCorners(3);
        if (worst.length > 0) {
            StringBuilder sb = new StringBuilder("Donde más tiempo pierdes: ");
            for (int k = 0; k < worst.length; k++) {
                int c = worst[k];
                sb.append(k == 0 ? "" : k == worst.length - 1 ? " y " : ", ").append("curva ").append(c + 1)
                  .append(", ").append(Engineer.speakDelta(avgLoss(c))).append(" por vuelta");
            }
            out.add(sb.append(".").toString());
        }
        addType(out, Dynamics.LOCK, "Bloqueaste ruedas", "frena un poco menos fuerte al inicio o suelta antes el freno", false);
        addType(out, Dynamics.SPIN, "Patinaste", "dosifica el acelerador a la salida", false);
        addType(out, Dynamics.OVER, "Tendencia a sobreviraje (se va la cola)", "acelera más suave en el vértice; si sigue, sube un punto el TCS", true);
        addType(out, Dynamics.UNDER, "Tendencia a subviraje (el auto no dobla)", "entra más lento y suelta el freno de a poco; si sigue, balance de frenos un punto atrás", true);
        if (topKmh > 0) out.add("Velocidad máxima: " + Math.round(topKmh) + " kilómetros por hora.");
        if (worst.length > 0) {
            int c = worst[0];
            float dv = bestMinV[c] - lastMinV[c];
            String nx = "Para la próxima: concéntrate en la curva " + (c + 1);
            if (dv > 3) nx += "; en tu mejor paso llevaste " + Math.round(dv) + " kilómetros por hora más en el vértice";
            out.add(nx + ".");
        }
        return out;
    }

    /** Resumen hablado (los puntos seguidos). */
    String debrief() {
        StringBuilder sb = new StringBuilder("Resumen de la carrera. ");
        for (String s : debriefItems()) sb.append(s).append(' ');
        return sb.toString().trim();
    }

    private void addType(ArrayList<String> out, int type, String what, String fix, boolean onlyTrend) {
        int n = count(type);
        if (n == 0) return;
        int c = worstCornerFor(type);
        if (onlyTrend && trendLaps(type) < 2) return;   // un caso aislado no es tendencia
        String s = what + ": " + n + (n == 1 ? " vez" : " veces");
        if (c >= 0) s += ", sobre todo en la curva " + (c + 1);
        out.add(s + ". Consejo: " + fix + ".");
    }

    String csv() {
        StringBuilder sb = new StringBuilder("vuelta,tiempo,tiempo_ms,sector1_ms,sector2_ms,sector3_ms,boxes,vel_max_kmh,combustible_pct,bloqueos,patinajes,sobreviraje,subviraje\n");
        for (Lap l : laps)
            sb.append(l.lap).append(',').append(Engineer.msText(l.ms)).append(',').append(l.ms).append(',')
              .append(l.s1 > 0 ? String.valueOf(l.s1) : "").append(',').append(l.s2 > 0 ? String.valueOf(l.s2) : "").append(',')
              .append(l.s3 > 0 ? String.valueOf(l.s3) : "").append(',').append(l.pit ? "si" : "").append(',')
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
