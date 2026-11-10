package cl.eleva.gt7;

/**
 * Dinámica del auto a partir de la telemetría: fuerzas G, deslizamiento de cada rueda
 * (bloqueos al frenar y patinaje al acelerar), sobreviraje (la carrocería gira más que la trayectoria)
 * y subviraje (con el volante del paquete "B": mucho volante para poca curva).
 */
final class Dynamics {
    static final int LOCK = 0, SPIN = 1, OVER = 2, UNDER = 3;
    static final String[] WHEEL = {"delantera izquierda", "delantera derecha", "trasera izquierda", "trasera derecha"};

    // ---- estado visible ----
    float gLat, gLon;                 // G (lat +: hacia la derecha del auto; lon +: acelerando)
    final float[] slip = new float[4];        // velocidad de la rueda / velocidad del auto - 1
    final float[] trailLat = new float[90], trailLon = new float[90];
    int trailN, trailPos;
    float maxGLat, maxGBrake, maxGAcc;
    float yawExcess;                  // rad/s
    float understeerRatio;            // volante usado / volante "normal" para esa curva (1 = neutro)
    boolean steerAvailable;

    // ---- eventos de este paquete ----
    int evType = -1, evWheel = -1, evWheels;   // evWheels: bits de ruedas involucradas

    private float pvx, pvz, ph;
    private boolean havePrev;
    private float axS, azS, rateS, excessS, steerS, angS;
    private final int[] lockN = new int[4], spinN = new int[4];
    private final boolean[] lockOn = new boolean[4], spinOn = new boolean[4];
    private int overN, underN;
    private boolean overOn, underOn;
    float baseK; int baseN; float dbgKap;
    private int frame;

    void reset() {
        havePrev = false; trailN = 0; trailPos = 0; maxGLat = maxGBrake = maxGAcc = 0;
        baseK = 0; baseN = 0; steerS = 0; overOn = underOn = false; overN = underN = 0;
        for (int i = 0; i < 4; i++) { lockN[i] = spinN[i] = 0; lockOn[i] = spinOn[i] = false; slip[i] = 0; }
    }

    /** Procesa un paquete. dt en segundos. Deja en evType el evento detectado (o -1). */
    void update(Telemetry t, float dt, boolean running) {
        evType = -1; evWheel = -1; evWheels = 0;
        steerAvailable = t.hasSteer;
        float v = t.speedMs;
        if (!running || dt <= 0) { havePrev = false; return; }
        float h = (float) Math.atan2(t.velZ, t.velX);
        if (havePrev && v > 3f) {
            float ax = (t.velX - pvx) / dt, az = (t.velZ - pvz) / dt;
            if (ax * ax + az * az > 60f * 60f) { ax = axS; az = azS; }   // salto (reaparición, cambio de vuelta): se ignora
            axS += (ax - axS) * 0.2f; azS += (az - azS) * 0.2f;
            float fx = t.velX / v, fz = t.velZ / v;
            gLon = (axS * fx + azS * fz) / 9.81f;
            gLat = (axS * -fz + azS * fx) / 9.81f;
            float dh = h - ph;
            while (dh > Math.PI) dh -= 2 * Math.PI;
            while (dh < -Math.PI) dh += 2 * Math.PI;
            rateS += (dh / dt - rateS) * 0.2f;
            steerS += (Math.abs(t.steer) - steerS) * 0.2f;   // mismo suavizado para que no haya desfase
            angS += (t.angVelY - angS) * 0.2f;   // mismo suavizado que la trayectoria
            float ex = Math.abs(angS) - Math.abs(rateS);
            excessS += (ex - excessS) * 0.25f;
            yawExcess = excessS;
            if (Math.abs(gLat) > maxGLat) maxGLat = Math.abs(gLat);
            if (-gLon > maxGBrake) maxGBrake = -gLon;
            if (gLon > maxGAcc) maxGAcc = gLon;
        } else { gLat = gLon = 0; }
        pvx = t.velX; pvz = t.velZ; ph = h; havePrev = true;
        if ((frame++ & 1) == 0) {
            trailLat[trailPos] = gLat; trailLon[trailPos] = gLon;
            trailPos = (trailPos + 1) % trailLat.length;
            if (trailN < trailLat.length) trailN++;
        }

        // ---- ruedas ----
        int lockBits = 0, spinBits = 0;
        for (int i = 0; i < 4; i++) {
            float r = t.tyreRadius[i];
            if (r < 0.1f || r > 1f || v < 3f) { slip[i] = 0; lockN[i] = spinN[i] = 0; continue; }
            float ws = Math.abs(t.wheelRps[i]) * r;
            slip[i] = ws / v - 1f;
            boolean locking = t.brake > 40 && v > 8f && ws < 0.7f * v;
            lockN[i] = locking ? lockN[i] + 1 : 0;
            if (lockN[i] >= 5 && !lockOn[i]) { lockOn[i] = true; lockBits |= 1 << i; }
            if (!locking && (t.brake < 20 || ws > 0.9f * v)) lockOn[i] = false;
            boolean spinning = t.throttle > 120 && ws > 1.2f * v + 0.5f;
            spinN[i] = spinning ? spinN[i] + 1 : 0;
            if (spinN[i] >= 8 && !spinOn[i]) { spinOn[i] = true; spinBits |= 1 << i; }
            if (!spinning && (t.throttle < 80 || ws < 1.08f * v)) spinOn[i] = false;
        }
        if (lockBits != 0) { evType = LOCK; evWheels = lockBits; evWheel = Integer.numberOfTrailingZeros(lockBits); return; }
        if (spinBits != 0) { evType = SPIN; evWheels = spinBits; evWheel = Integer.numberOfTrailingZeros(spinBits); return; }

        // ---- sobreviraje ----
        boolean over = v > 15f && excessS > 0.2f;
        overN = over ? overN + 1 : 0;
        if (overN >= 9 && !overOn) { overOn = true; evType = OVER; return; }
        if (excessS < 0.08f) overOn = false;

        // ---- subviraje (sólo con volante) ----
        if (t.hasSteer && v > 12f) {
            float kap = Math.abs(rateS) / v; dbgKap = kap;
            if (kap > 0.003f) {
                float k = steerS / kap;
                float g = Math.abs(gLat);
                if (g > 0.15f && g < 0.7f) learnBase(k);
                understeerRatio = baseN >= baseBuf.length && baseK > 0 ? k / baseK : 0;
                boolean under = baseN >= baseBuf.length && g > 0.6f && understeerRatio > 1.6f;
                underN = under ? underN + 1 : 0;
                if (underN >= 18 && !underOn) { underOn = true; evType = UNDER; return; }
                if (understeerRatio < 1.25f) underOn = false;
            } else { underN = 0; understeerRatio = 0; underOn = false; }
        }
    }

    private final float[] baseBuf = new float[61];

    /** Volante "normal" por unidad de curvatura: mediana de las primeras muestras y luego promedio robusto. */
    private void learnBase(float k) {
        if (baseN < baseBuf.length) {
            baseBuf[baseN++] = k;
            if (baseN == baseBuf.length) {
                float[] c = baseBuf.clone();
                java.util.Arrays.sort(c);
                baseK = c[c.length / 2];
            }
            return;
        }
        if (k > baseK * 0.6f && k < baseK * 1.6f) baseK += (k - baseK) * 0.01f;
        baseN++;
    }

    /** "la delantera izquierda" / "las delanteras" / "las traseras"... */
    static String wheels(int bits) {
        if (bits == 3) return "las dos delanteras";
        if (bits == 12) return "las dos traseras";
        if (Integer.bitCount(bits) > 2) return "varias ruedas";
        if (Integer.bitCount(bits) == 2) return "dos ruedas";
        return "la " + WHEEL[Integer.numberOfTrailingZeros(bits)];
    }
}
