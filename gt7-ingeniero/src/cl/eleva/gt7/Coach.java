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
    int mapIdx = -1;
    float offLine = -1;      // metros entre el auto y la línea de la mejor vuelta (-1 = sin referencia)
    float[] fixedS, fixedE;  // curvas de un circuito ya conocido (fracción de vuelta); null = detectar          // índice de la mejor vuelta que corresponde a la posición actual

    // curvas de la referencia
    int nc;
    int[] cStart = new int[0];
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

    // ventanas de evaluación de cada curva (distancia sobre la referencia)
    private float[] wStart = new float[0], wEnd = new float[0];

    /**
     * Detecta curvas por la geometría de la pista (cambio de rumbo), no sólo por las frenadas:
     * así una chicana o unas curvas enlazadas cuentan como curvas separadas.
     */
    private void detectCorners() {
        Trace r = ref;
        if (fixedS != null && r.n > 50) {
            float len = r.d[r.n - 1];
            int n = fixedS.length;
            int[] si = new int[n], ei = new int[n];
            for (int c = 0; c < n; c++) { si[c] = idxAt(r, fixedS[c] * len, 0); ei[c] = idxAt(r, fixedE[c] * len, si[c]); }
            buildCorners(si, ei, n);
            return;
        }
        final float STEP = 5f;
        float len = r.d[r.n - 1];
        int m = (int) (len / STEP);
        if (m < 20) { nc = 0; alloc(0); return; }
        // re-muestrea cada 5 m
        float[] px = new float[m], pz = new float[m];
        int[] idx = new int[m];
        int j = 0;
        for (int k = 0; k < m; k++) {
            float d = k * STEP;
            while (j < r.n - 1 && r.d[j] < d) j++;
            px[k] = r.x[j]; pz[k] = r.z[j]; idx[k] = j;
        }
        // curvatura (rad/m) suavizada
        float[] kap = new float[m];
        for (int k = 1; k < m - 2; k++) {
            double h0 = Math.atan2(pz[k] - pz[k - 1], px[k] - px[k - 1]);
            double h1 = Math.atan2(pz[k + 2] - pz[k + 1], px[k + 2] - px[k + 1]);
            double dh = h1 - h0;
            while (dh > Math.PI) dh -= 2 * Math.PI;
            while (dh < -Math.PI) dh += 2 * Math.PI;
            kap[k] = (float) (dh / (3 * STEP));
        }
        float[] sm = new float[m];
        for (int k = 2; k < m - 2; k++) sm[k] = (kap[k - 2] + kap[k - 1] + kap[k] + kap[k + 1] + kap[k + 2]) / 5f;
        final float K_ON = 1f / 220f;   // radio menor a ~220 m = curva
        int[] cs = new int[128], ce = new int[128];
        int n = 0, k = 0;
        while (k < m && n < 128) {
            if (Math.abs(sm[k]) > K_ON) {
                int sign = sm[k] > 0 ? 1 : -1, st = k;
                float turn = 0;
                while (k < m && Math.abs(sm[k]) > K_ON * 0.6f && (sm[k] > 0 ? 1 : -1) == sign) { turn += Math.abs(sm[k]) * STEP; k++; }
                if (turn > 0.35f) {   // más de ~20° de giro
                    // une con la anterior si gira para el mismo lado y casi sin recta entre medio
                    if (n > 0 && (st - ce[n - 1]) * STEP < 20f && Math.signum(sm[ce[n - 1] - 1]) == sign) ce[n - 1] = k;
                    else { cs[n] = st; ce[n] = k; n++; }
                }
            } else k++;
        }
        int[] si = new int[n], ei = new int[n];
        for (int c = 0; c < n; c++) { si[c] = idx[cs[c]]; ei[c] = idx[Math.min(m - 1, ce[c])]; }
        buildCorners(si, ei, n);
    }

    /** Fracciones de vuelta (inicio, fin) de cada curva actual, para guardar el circuito. */
    float[][] segments() {
        float len = refLength();
        float[] a = new float[nc], b = new float[nc];
        for (int c = 0; c < nc; c++) { a[c] = ref.d[cStart[c]] / len; b[c] = ref.d[cExit[c]] / len; }
        return new float[][]{a, b};
    }

    /** Usa las curvas de un circuito conocido (misma numeración que la vez anterior). */
    void useSegments(float[] fs, float[] fe) {
        fixedS = fs; fixedE = fe;
        if (ref != null) { detectCorners(); nextCorner = 0; }
    }

    private void buildCorners(int[] si, int[] ei, int n) {
        Trace r = ref;
        alloc(n);
        nc = n;
        for (int c = 0; c < n; c++) {
            int s0 = si[c], e0 = Math.max(si[c], ei[c]);
            cStart[c] = s0;
            int prevEnd = c > 0 ? ei[c - 1] : 0;
            int apex = s0;
            for (int q = s0; q <= e0; q++) if (r.v[q] < r.v[apex]) apex = q;
            // frenada que pertenece a esta curva: hasta 250 m antes, sin pasar la curva anterior
            int b = -1;
            float from = Math.max(r.d[prevEnd], r.d[s0] - 250f);
            for (int q = idxAt(r, from, prevEnd); q <= apex; q++) if (r.brk(q) > BRAKE_ON) { b = q; break; }
            if (b >= 0 && r.v[b] - r.v[apex] < 8f) b = -1;  // toque sin efecto
            cBrake[c] = b; cApex[c] = apex; cExit[c] = e0; cMinV[c] = r.v[apex];
            int f = apex;
            while (f < r.n - 1 && r.thr(f) < FULL_THROTTLE) f++;
            cFull[c] = f;
            cExitGear[c] = r.gear[idxAt(r, r.d[e0] + 40f, e0)];
            wStart[c] = Math.max(r.d[prevEnd], (b >= 0 ? r.d[b] : r.d[s0]) - (b >= 0 ? 150f : 60f));
            brakeD[c] = -1; minV[c] = 1e9f; fullD[c] = -1;
        }
        for (int c = 0; c < n; c++) {
            float end = r.d[cExit[c]] + 40f;
            if (c + 1 < n) end = Math.min(end, Math.max(r.d[cExit[c]], wStart[c + 1]));
            wEnd[c] = end;
            if (c + 1 < n && wStart[c + 1] < r.d[cExit[c]]) wStart[c + 1] = r.d[cExit[c]];
        }
    }

    private void alloc(int k) {
        cStart = new int[k]; cBrake = new int[k]; cApex = new int[k]; cExit = new int[k]; cFull = new int[k]; cExitGear = new int[k]; cMinV = new float[k];
        brakeD = new float[k]; minV = new float[k]; fullD = new float[k]; deltaIn = new float[k];
        seen = new boolean[k]; done = new boolean[k]; wStart = new float[k]; wEnd = new float[k];
    }

    private static int idxAt(Trace r, float dist, int from) {
        int i = from;
        while (i < r.n - 1 && r.d[i] < dist) i++;
        return i;
    }

    /** Ubica la posición actual sobre la mejor vuelta (búsqueda local del punto más cercano). */
    private void map(float px, float pz) {
        if (ref == null) { mapIdx = -1; offLine = -1; return; }
        int from, to;
        if (mapIdx < 0) { from = 0; to = ref.n - 1; }
        else { from = Math.max(0, mapIdx - 30); to = Math.min(ref.n - 1, mapIdx + 300); }
        int best = -1;
        float bd = Float.MAX_VALUE;
        for (int i = from; i <= to; i++) {
            float dx = ref.x[i] - px, dz = ref.z[i] - pz, dd = dx * dx + dz * dz;
            if (dd < bd) { bd = dd; best = i; }
        }
        offLine = best >= 0 ? (float) Math.sqrt(bd) : -1;
        if (best >= 0 && bd < 60f * 60f) mapIdx = best;
    }

    /**
     * Agrega una muestra de la vuelta actual. Devuelve un consejo cuando se termina de pasar una curva
     * (o null). lapTime en segundos.
     */
    // resultado de la última curva evaluada (para el ingeniero y el historial)
    boolean evaluatedNow;
    int lastCorner = -1;
    float lastGain, lastMinKmh;

    /** Curva en la que está el auto ahora (índice desde 0), o -1 en recta / sin referencia. */
    int cornerNow() {
        if (ref == null || mapIdx < 0 || nextCorner >= nc) return -1;
        float rd = ref.d[mapIdx];
        return rd >= wStart[nextCorner] ? nextCorner : -1;
    }

    String sample(Telemetry t, float lapTime, float dist) {
        evaluatedNow = false;
        cur.add(t.posX, t.posZ, dist, lapTime, t.kmh(), t.throttle, t.brake, t.gear);
        if (ref == null) return null;
        map(t.posX, t.posZ);
        if (mapIdx < 0 || nextCorner >= nc) return null;
        float rd = ref.d[mapIdx];
        int c = nextCorner;
        float winStart = wStart[c], winEnd = wEnd[c];
        if (rd < winStart) return null;
        float delta = lapTime - ref.t[mapIdx];
        if (!seen[c]) { seen[c] = true; deltaIn[c] = delta; }
        if (t.brake > BRAKE_ON && brakeD[c] < 0) brakeD[c] = rd;
        if (rd < ref.d[cExit[c]] + 20f) minV[c] = Math.min(minV[c], t.kmh());
        if (rd > ref.d[cApex[c]] && t.throttle >= FULL_THROTTLE && t.brake <= BRAKE_ON && fullD[c] < 0) fullD[c] = rd;
        if (rd < winEnd) return null;
        done[c] = true;
        nextCorner++;
        evaluatedNow = true; lastCorner = c; lastGain = delta - deltaIn[c]; lastMinKmh = minV[c] < 1e8f ? minV[c] : 0;
        return advice(c, lastGain, t.gear);
    }

    static String gearName(int g) {
        String[] n = {"reversa", "primera", "segunda", "tercera", "cuarta", "quinta", "sexta", "séptima", "octava"};
        return g >= 0 && g < n.length ? n[g] : String.valueOf(g);
    }

    private static int m5(float m) { return Math.max(5, Math.round(Math.abs(m) / 5f) * 5); }

    /** Arma el consejo de la curva c; gained: segundos perdidos (+) o ganados (-) en la curva. */
    String advice(int c, float gained, int exitGear) {
        String name = "Curva " + (c + 1) + ": ";
        boolean refBraked = cBrake[c] >= 0;
        float brakeDiff = refBraked && brakeD[c] >= 0 ? brakeD[c] - ref.d[cBrake[c]] : 0;   // + frenaste más tarde
        float vDiff = minV[c] < 1e8f ? minV[c] - cMinV[c] : 0;       // + más rápido en el vértice
        float fullDiff = fullD[c] >= 0 ? fullD[c] - ref.d[cFull[c]] : 0; // + aceleraste más tarde
        boolean gearDiff = exitGear != cExitGear[c] && cExitGear[c] > 0 && exitGear > 0 && exitGear < 15;
        String gearTip = gearDiff ? " y sal en " + gearName(cExitGear[c]) : "";

        if (gained >= 0.12f) {
            if (!refBraked && brakeD[c] >= 0)
                return name + "en tu mejor vuelta la pasaste sin frenar, sólo levantando. Perdiste " + Engineer.speakDelta(gained) + ".";
            if (brakeD[c] >= 0 && brakeDiff < -12f && vDiff <= 3f)
                return name + "frena " + m5(brakeDiff) + " metros más tarde" + gearTip + ". Perdiste " + Engineer.speakDelta(gained) + ".";
            if (brakeDiff > 12f && vDiff < -4f)
                return name + "frenaste " + m5(brakeDiff) + " metros tarde y pasaste lento por el vértice. Frena un poco antes" + gearTip + ".";
            if (vDiff < -5f)
                return name + "pasaste " + Math.round(-vDiff) + " kilómetros por hora más lento por el vértice. Suelta antes el freno" + gearTip + ".";
            if (fullDiff > 15f)
                return name + "aceleraste a fondo " + m5(fullDiff) + " metros más tarde. Acelera antes a la salida" + gearTip + ".";
            if (gearDiff)
                return name + "en tu mejor vuelta saliste en " + gearName(cExitGear[c]) + " y ahora en " + gearName(exitGear) + ".";
            return name + "perdiste " + Engineer.speakDelta(gained) + ".";
        }
        if (gained <= -0.25f) {
            String why = brakeDiff > 8f ? ", frenando más tarde" : vDiff > 4f ? ", con más velocidad en el vértice" : fullDiff < -10f ? ", acelerando antes" : "";
            return name + "ganaste " + Engineer.speakDelta(-gained) + why + ". Así.";
        }
        return null;
    }
}
