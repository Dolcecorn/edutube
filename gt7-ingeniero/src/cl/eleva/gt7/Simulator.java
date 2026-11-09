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

    private final float[] tx = new float[(int) LAP_M + 2], tz = new float[(int) LAP_M + 2];

    private final float fuelRate;

    Simulator() { this(12f); }

    Simulator(float fuelPerLap) {
        fuelRate = fuelPerLap;
        // trazado fijo: curva donde la velocidad objetivo es baja; el lado cambia para formar chicanas
        double h = 0, x = 0, z = 0;
        for (int i = 0; i < tx.length; i++) {
            double a = 2 * Math.PI * i / LAP_M;
            double v = 24 + 46 * (0.5 + 0.5 * Math.sin(a * 5) * Math.cos(a * 2));
            double k = Math.max(0, 50 - v) / 50.0 * 0.03 * (Math.sin(a * 13) >= 0 ? 1 : -1);
            h += k;
            x += Math.cos(h); z += Math.sin(h);
            tx[i] = (float) x; tz[i] = (float) z;
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
        t.timeOfDayMs += 17;
        return t.encode(0x1234567 + pid * 7919);
    }
}
