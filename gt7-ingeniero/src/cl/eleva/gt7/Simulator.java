package cl.eleva.gt7;

import java.util.Random;

/** Genera una carrera falsa (10 vueltas, ~80 s cada una) para el modo demostración y las pruebas. */
final class Simulator {
    static final float LAP_M = 3000f;
    private final Random rnd = new Random(7);
    private final Telemetry t = new Telemetry();
    private int pid = 1000;
    private float dist, lapTime, pace = 1f, preRace = 3f, shift;
    private int best = -1;
    private float heat;
    int pitAt = 6;                 // entra a boxes al final de esta vuelta (0 = nunca)
    private float stopT;
    private boolean stopDone;

    private final float[] tx = new float[(int) LAP_M + 2], tz = new float[(int) LAP_M + 2], th = new float[(int) LAP_M + 2], tk = new float[(int) LAP_M + 2];

    private final float fuelRate;

    Simulator() { this(12f); }

    Simulator(float fuelPerLap) {
        fuelRate = fuelPerLap;
        // trazado fijo: curva donde la velocidad objetivo es baja; el lado cambia para formar chicanas
        double[] ks = new double[tx.length];
        double sum = 0;
        for (int i = 0; i < tx.length; i++) {
            double a = 2 * Math.PI * i / LAP_M;
            double v = 24 + 46 * (0.5 + 0.5 * Math.sin(a * 5) * Math.cos(a * 2));
            ks[i] = Math.max(0, 50 - v) / 50.0 * 0.03 * (Math.sin(a * 13) >= -0.35 ? 1 : -1);
            sum += ks[i];
        }
        double scale = 2 * Math.PI / sum;   // que el trazado dé una vuelta completa
        double h = 0, x = 0, z = 0;
        for (int i = 0; i < tx.length; i++) {
            double k = ks[i] * scale;
            h += k;
            x += Math.cos(h); z += Math.sin(h);
            tx[i] = (float) x; tz[i] = (float) z; th[i] = (float) h; tk[i] = (float) k;
        }
        t.fuelCapacity = 100f; t.fuel = 100f; t.totalLaps = 10; t.lap = 0; t.bestLapMs = -1; t.lastLapMs = -1;
        t.rpmAlertMin = 6500; t.rpmAlertMax = 7600; t.waterTemp = 85; t.oilTemp = 95; t.oilPressure = 4.5f;
        t.flags = Telemetry.FLAG_ON_TRACK | Telemetry.FLAG_IN_GEAR | Telemetry.FLAG_TURBO;
        t.carCode = 3337;
        for (int i = 0; i < 4; i++) t.tyreTemp[i] = 60f;
    }

    private float target(float s) {
        double a = 2 * Math.PI * (s + shift) / LAP_M;
        return (float) (24 + 46 * (0.5 + 0.5 * Math.sin(a * 5) * Math.cos(a * 2))) * pace;
    }

    private boolean pitZone() {
        if (pitAt <= 0 || preRace > 0 || t.lap > t.totalLaps) return false;
        return (t.lap == pitAt && dist > LAP_M - 400) || (t.lap == pitAt + 1 && dist < 400);
    }

    /** Avanza 1/60 s y devuelve el paquete cifrado. */
    byte[] next() {
        float dt = 1f / Engineer.HZ;
        pid++;
        t.packetId = pid;
        if (preRace > 0) {
            preRace -= dt;
            t.speedMs = 0; t.rpm = 1200 + rnd.nextFloat() * 300; t.gear = 1; t.throttle = 40; t.brake = 0;
            if (preRace <= 0) { t.lap = 1; pace = 0.97f; }
        } else {
            boolean finished = t.lap > t.totalLaps;
            float v = finished ? Math.max(8f, t.speedMs - 4 * dt) : target(dist);
            if (pitZone()) v = Math.min(v, 16.7f);            // límite de velocidad del pit lane
            if (stopT > 0) {                                   // detenido: repostaje
                stopT -= dt; v = 0; t.speedMs = 0;
                t.fuel = Math.min(100f, t.fuel + 8f * dt);
                if (stopT <= 0) stopDone = true;
            } else if (pitAt > 0 && t.lap == pitAt + 1 && dist > 150 && !stopDone) { stopT = 8f; v = 0; t.speedMs = 0; }
            float acc = (v - t.speedMs) / dt;
            t.speedMs += Math.max(-25f, Math.min(9f, acc)) * dt;
            t.throttle = acc > -1 ? (int) Math.min(255, 140 + acc * 15) : 0;
            t.brake = acc < -3 ? (int) Math.min(255, 60 - acc * 8) : 0;
            dist += t.speedMs * dt; lapTime += dt;
            float kmh = t.kmh();
            t.gear = Math.max(1, Math.min(6, 1 + (int) (kmh / 45f)));
            float inGear = (kmh - (t.gear - 1) * 45f) / 45f;
            t.rpm = t.gear == 6 ? 4000 + kmh * 12 : 3800 + inGear * 4000;
            t.suggestedGear = 15;
            if (t.fuel > 0) t.fuel -= fuelRate * t.speedMs * dt / LAP_M;  // ~12 % por vuelta: no alcanza
            heat += ((t.brake > 0 ? 1.5f : 0) + Math.abs(acc) * 0.02f - 0.4f) * dt;
            heat = Math.max(0, Math.min(1.6f, heat));
            for (int i = 0; i < 4; i++) {
                float base = 72 + 10 * Math.min(1, lapTime / 30f) + heat * (i == 0 ? 16 : i == 1 ? 10 : 6);
                t.tyreTemp[i] += (base - t.tyreTemp[i]) * dt * 0.5f;
            }
            if (!finished && dist >= LAP_M) {
                dist -= LAP_M;
                int ms = Math.round(lapTime * 1000);
                t.lastLapMs = ms;
                if (best < 0 || ms < best) best = ms;
                t.bestLapMs = best;
                t.lap++;
                lapTime = 0;
                pace = 0.985f + rnd.nextFloat() * 0.03f;
                shift = (rnd.nextFloat() - 0.5f) * 50f;   // frena hasta 25 m antes o después
            }
        }
        int di = Math.max(0, Math.min(tx.length - 1, (int) dist));
        t.posX = tx[di]; t.posZ = tz[di];
        if (pitZone()) { t.posX -= (float) Math.sin(th[di]) * 20f; t.posZ += (float) Math.cos(th[di]) * 20f; }  // pit lane al lado
        // dinámica: velocidad, giro, ruedas, suspensión y volante (paquete "B")
        float v = t.speedMs, k = tk[di];
        t.velX = (float) Math.cos(th[di]) * v; t.velZ = (float) Math.sin(th[di]) * v;
        t.angVelY = k * v;
        t.steer = (float) Math.atan(k * 2.6) * 14f;
        for (int i = 0; i < 4; i++) {
            t.tyreRadius[i] = 0.33f;
            t.wheelRps[i] = v / 0.33f;
            t.suspHeight[i] = 0.07f + (i < 2 ? -1 : 1) * (t.brake / 255f) * 0.015f + (i % 2 == 0 ? 1 : -1) * k * 0.4f;
        }
        t.bodyHeight = 0.08f;
        boolean firstHalf = dist < LAP_M / 2;
        if (t.lap > 1 && t.lap % 3 == 0 && firstHalf && t.brake > 150) t.wheelRps[0] *= 0.4f;       // bloqueo DI
        if (t.lap > 1 && t.lap % 4 == 0 && !firstHalf && t.throttle > 200 && t.kmh() < 140) {        // patinaje
            t.wheelRps[2] *= 1.35f; t.wheelRps[3] *= 1.35f;
        }
        if (t.lap >= 5 && t.lap <= 7 && Math.abs(k) > 0.006f && dist > 1000 && dist < 2000) t.angVelY = k * v + 0.45f * Math.signum(k); // sobreviraje
        if (t.lap == 8 && Math.abs(k) > 0.006f && dist > 1500) t.steer *= 2.0f;                       // subviraje
        t.timeOfDayMs += 17;
        return t.encode(0x1234567 + pid * 7919, true);
    }
}
