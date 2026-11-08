package cl.eleva.gt7;

/**
 * Entrenador por curvas: guarda la traza de la mejor vuelta (posición, velocidad, pedales, marcha),
 * detecta las zonas de frenada (curvas) y compara cada curva de la vuelta actual contra ella.
 * Las curvas se numeran en orden desde la línea de meta: 1 = la primera frenada fuerte.
 */
final class Coach {
    static final class Trace {
        float[] x = new float[8192], z = new float[8192], d = new float[8192], t = new float[8192], v = new float[8192];
        byte[] thr = new byte[8192], brk = new byte[8192], gear = new byte[8192];
        int n;

        void add(float px, float pz, float dist, float time, float kmh, int throttle, int brake, int g) {
            if (n == x.length) grow();
            x[n] = px; z[n] = pz; d[n] = dist; t[n] = time; v[n] = kmh;
            thr[n] = (byte) throttle; brk[n] = (byte) brake; gear[n] = (byte) g;
            n++;
        }

        private void grow() {
            int m = n * 2;
            x = cp(x, m); z = cp(z, m); d = cp(d, m); t = cp(t, m); v = cp(v, m);
            thr = cp(thr, m); brk = cp(brk, m); gear = cp(gear, m);
        }
        private static float[] cp(float[] a, int m) { float[] r = new float[m]; System.arraycopy(a, 0, r, 0, a.length); return r; }
        private static byte[] cp(byte[] a, int m) { byte[] r = new byte[m]; System.arraycopy(a, 0, r, 0, a.length); return r; }
        int thr(int i) { return thr[i] & 0xff; }
        int brk(int i) { return brk[i] & 0xff; }
    }

    static final int BRAKE_ON = 40, FULL_THROTTLE = 245;

    Trace cur = new Trace(), last, ref;
    int mapIdx = -1;          // índice de la mejor vuelta que corresponde a la posición actual

    // curvas de la referencia
    int nc;
    int[] cBrake = new int[0], cApex = new int[0], cExit = new int[0], cFull = new int[0], cExitGear = new int[0];
    float[] cMinV = new float[0];

    // estado de la vuelta actual por curva
    private float[] brakeD = new float[0], minV = new float[0], fullD = new float[0], deltaIn = new float[0];
    private boolean[] seen = new boolean[0], done = new boolean[0];
    private int nextCorner;

    void startLap() {
        Trace tmp = last != null && last != ref ? last : new Trace();
        last = cur;
        cur = tmp; cur.n = 0;
        mapIdx = ref != null ? 0 : -1;
        nextCorner = 0;
        for (int i = 0; i < nc; i++) { brakeD[i] = -1; minV[i] = 1e9f; fullD[i] = -1; seen[i] = false; done[i] = false; }
    }

    /** La vuelta recién terminada (last) es la nueva mejor: pasa a ser la referencia. */
    void adoptLast() {
        if (last == null || last.n < 200) return;
        ref = last;
        last = null;
        detectCorners();
        mapIdx = 0;        // la vuelta en curso recién empieza
        nextCorner = 0;
    }

    float refLength() { return ref == null || ref.n == 0 ? 0 : ref.d[ref.n - 1]; }

    private void detectCorners() {
        Trace r = ref;
        int[] b = new int[64], a = new int[64], e = new int[64];
        int k = 0;
        int i = 0;
        while (i < r.n && k < 64) {
            if (r.brk(i) > BRAKE_ON && (i == 0 || r.brk(i - 1) <= BRAKE_ON)) {
                int start = i, apex = i, j = i, fullRun = 0;
                while (j < r.n) {
                    if (r.v[j] < r.v[apex]) apex = j;
                    fullRun = r.thr(j) >= FULL_THROTTLE && r.brk(j) <= BRAKE_ON ? fullRun + 1 : 0;
                    if (fullRun > 20 && j > apex) break;
                    j++;
                }
                int exit = Math.min(j, r.n - 1);
                // ignora toques de freno que no bajan la velocidad
                if (r.v[start] - r.v[apex] > 12f) {
                    if (k > 0 && r.d[start] - r.d[e[k - 1]] < 60f) { // une con la curva anterior (frenada en dos tiempos)
                        if (r.v[apex] < r.v[a[k - 1]]) a[k - 1] = apex;
                        e[k - 1] = exit;
                    } else { b[k] = start; a[k] = apex; e[k] = exit; k++; }
                }
                i = Math.max(exit, i + 1);
            } else i++;
        }
        nc = k;
        cBrake = new int[k]; cApex = new int[k]; cExit = new int[k]; cFull = new int[k]; cExitGear = new int[k]; cMinV = new float[k];
        brakeD = new float[k]; minV = new float[k]; fullD = new float[k]; deltaIn = new float[k];
        seen = new boolean[k]; done = new boolean[k];
        for (int c = 0; c < k; c++) {
            cBrake[c] = b[c]; cApex[c] = a[c]; cExit[c] = e[c]; cMinV[c] = r.v[a[c]];
            int f = a[c];
            while (f < r.n - 1 && r.thr(f) < FULL_THROTTLE) f++;
            cFull[c] = f;
            cExitGear[c] = r.gear[idxAt(r, r.d[e[c]] + 40f, e[c])];
            brakeD[c] = -1; minV[c] = 1e9f; fullD[c] = -1;
        }
    }

    private static int idxAt(Trace r, float dist, int from) {
        int i = from;
        while (i < r.n - 1 && r.d[i] < dist) i++;
        return i;
    }

    /** Ubica la posición actual sobre la mejor vuelta (búsqueda local del punto más cercano). */
    private void map(float px, float pz) {
        if (ref == null) { mapIdx = -1; return; }
        int from, to;
        if (mapIdx < 0) { from = 0; to = ref.n - 1; }
        else { from = Math.max(0, mapIdx - 30); to = Math.min(ref.n - 1, mapIdx + 300); }
        int best = -1;
        float bd = Float.MAX_VALUE;
        for (int i = from; i <= to; i++) {
            float dx = ref.x[i] - px, dz = ref.z[i] - pz, dd = dx * dx + dz * dz;
            if (dd < bd) { bd = dd; best = i; }
        }
        if (best >= 0 && bd < 60f * 60f) mapIdx = best;
    }

    /**
     * Agrega una muestra de la vuelta actual. Devuelve un consejo cuando se termina de pasar una curva
     * (o null). lapTime en segundos.
     */
    String sample(Telemetry t, float lapTime, float dist) {
        cur.add(t.posX, t.posZ, dist, lapTime, t.kmh(), t.throttle, t.brake, t.gear);
        if (ref == null) return null;
        map(t.posX, t.posZ);
        if (mapIdx < 0 || nextCorner >= nc) return null;
        float rd = ref.d[mapIdx];
        int c = nextCorner;
        float winStart = ref.d[cBrake[c]] - 150f;
        if (c > 0) winStart = Math.max(winStart, ref.d[cExit[c - 1]]);
        float winEnd = ref.d[cExit[c]] + 40f;
        if (rd < winStart) return null;
        float delta = lapTime - ref.t[mapIdx];
        if (!seen[c]) { seen[c] = true; deltaIn[c] = delta; }
        if (t.brake > BRAKE_ON && brakeD[c] < 0) brakeD[c] = rd;
        if (rd < ref.d[cExit[c]] + 20f) minV[c] = Math.min(minV[c], t.kmh());
        if (rd > ref.d[cApex[c]] && t.throttle >= FULL_THROTTLE && t.brake <= BRAKE_ON && fullD[c] < 0) fullD[c] = rd;
        if (rd < winEnd) return null;
        done[c] = true;
        nextCorner++;
        return advice(c, delta - deltaIn[c], t.gear);
    }

    static String gearName(int g) {
        String[] n = {"reversa", "primera", "segunda", "tercera", "cuarta", "quinta", "sexta", "séptima", "octava"};
        return g >= 0 && g < n.length ? n[g] : String.valueOf(g);
    }

    private static int m5(float m) { return Math.max(5, Math.round(Math.abs(m) / 5f) * 5); }

    /** Arma el consejo de la curva c; gained: segundos perdidos (+) o ganados (-) en la curva. */
    String advice(int c, float gained, int exitGear) {
        String name = "Curva " + (c + 1) + ": ";
        float refB = ref.d[cBrake[c]];
        float brakeDiff = brakeD[c] >= 0 ? brakeD[c] - refB : 0;   // + frenaste más tarde
        float vDiff = minV[c] < 1e8f ? minV[c] - cMinV[c] : 0;       // + más rápido en el vértice
        float fullDiff = fullD[c] >= 0 ? fullD[c] - ref.d[cFull[c]] : 0; // + aceleraste más tarde
        boolean gearDiff = exitGear != cExitGear[c] && cExitGear[c] > 0 && exitGear > 0 && exitGear < 15;
        String gearTip = gearDiff ? " y sal en " + gearName(cExitGear[c]) : "";

        if (gained >= 0.12f) {
            if (brakeD[c] >= 0 && brakeDiff < -12f && vDiff <= 3f)
                return name + "frena " + m5(brakeDiff) + " metros más tarde" + gearTip + ". Perdiste " + Engineer.speakDelta(gained) + ".";
            if (brakeDiff > 12f && vDiff < -4f)
                return name + "frenaste " + m5(brakeDiff) + " metros tarde y pasaste lento por el vértice. Frena un poco antes" + gearTip + ".";
            if (vDiff < -5f)
                return name + "pasaste " + Math.round(-vDiff) + " kilómetros por hora más lento por el vértice. Suelta antes el freno" + gearTip + ".";
            if (fullDiff > 15f)
                return name + "aceleraste a fondo " + m5(fullDiff) + " metros más tarde. Acelera antes a la salida" + gearTip + ".";
            if (gearDiff)
                return name + "en tu mejor vuelta saliste en " + gearName(cExitGear[c]) + ", hoy en " + gearName(exitGear) + ".";
            return name + "perdiste " + Engineer.speakDelta(gained) + ".";
        }
        if (gained <= -0.25f) {
            String why = brakeDiff > 8f ? ", frenando más tarde" : vDiff > 4f ? ", con más velocidad en el vértice" : fullDiff < -10f ? ", acelerando antes" : "";
            return name + "ganaste " + Engineer.speakDelta(-gained) + why + ". Así.";
        }
        return null;
    }
}
