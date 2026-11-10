package cl.eleva.gt7;

/**
 * Un paquete de telemetría de Gran Turismo 7 (formato "A", 296 bytes, puerto 33740).
 * Desplazamientos según la documentación de la comunidad (gt7telemetry / PDTools).
 */
final class Telemetry {
    static final int PACKET_SIZE = 0x128;      // paquete "A"
    static final int PACKET_SIZE_B = 0x13C;    // paquete "B" (GT7 1.42+): agrega volante y aceleraciones
    static final int IV_XOR_B = 0xDEADBEEF;
    static final int MAGIC = 0x47375330; // "0S7G"
    static final byte[] KEY = "Simulator Interface Packet GT7 ver 0.0".substring(0, 32).getBytes();
    static final int IV_XOR = 0xDEADBEAF;

    float posX, posY, posZ;
    float velX, velY, velZ;           // m/s en coordenadas del mundo
    float angVelX, angVelY, angVelZ;  // rad/s (Y = giro de la carrocería)
    float bodyHeight;
    final float[] wheelRps = new float[4];     // rad/s
    final float[] tyreRadius = new float[4];   // m
    final float[] suspHeight = new float[4];   // m
    boolean hasSteer;     // sólo en paquetes "B"
    float steer;          // ángulo del volante en radianes
    float rpm;
    float fuel, fuelCapacity;
    float speedMs;
    float boost;          // bar (relativo a la atmósfera)
    float oilPressure, waterTemp, oilTemp;
    final float[] tyreTemp = new float[4];  // FL, FR, RL, RR (°C)
    int packetId;
    int lap, totalLaps;
    int bestLapMs, lastLapMs;
    int timeOfDayMs;
    int rpmAlertMin, rpmAlertMax;
    int flags;
    int gear, suggestedGear;
    int throttle, brake; // 0..255
    float clutch;
    int carCode;

    static final int FLAG_ON_TRACK = 1, FLAG_PAUSED = 2, FLAG_LOADING = 4, FLAG_IN_GEAR = 8,
            FLAG_TURBO = 16, FLAG_REV_LIMIT = 32, FLAG_HANDBRAKE = 64, FLAG_LIGHTS = 128,
            FLAG_ASM = 1024, FLAG_TCS = 2048;

    boolean onTrack() { return (flags & FLAG_ON_TRACK) != 0; }
    boolean paused() { return (flags & FLAG_PAUSED) != 0; }
    boolean loading() { return (flags & FLAG_LOADING) != 0; }
    boolean hasTurbo() { return (flags & FLAG_TURBO) != 0; }
    boolean revLimiter() { return (flags & FLAG_REV_LIMIT) != 0; }
    boolean tcs() { return (flags & FLAG_TCS) != 0; }
    boolean asm() { return (flags & FLAG_ASM) != 0; }
    float kmh() { return speedMs * 3.6f; }
    /** true si el auto usa combustible medible (no eléctrico / no infinito). */
    boolean hasFuel() { return fuelCapacity > 0f; }
    float fuelPct() { return fuelCapacity > 0 ? 100f * fuel / fuelCapacity : 0f; }

    void copyFrom(Telemetry o) {
        posX = o.posX; posY = o.posY; posZ = o.posZ; velX = o.velX; velY = o.velY; velZ = o.velZ;
        angVelX = o.angVelX; angVelY = o.angVelY; angVelZ = o.angVelZ; bodyHeight = o.bodyHeight;
        System.arraycopy(o.wheelRps, 0, wheelRps, 0, 4); System.arraycopy(o.tyreRadius, 0, tyreRadius, 0, 4);
        System.arraycopy(o.suspHeight, 0, suspHeight, 0, 4); hasSteer = o.hasSteer; steer = o.steer; rpm = o.rpm; fuel = o.fuel; fuelCapacity = o.fuelCapacity;
        speedMs = o.speedMs; boost = o.boost; oilPressure = o.oilPressure; waterTemp = o.waterTemp; oilTemp = o.oilTemp;
        System.arraycopy(o.tyreTemp, 0, tyreTemp, 0, 4);
        packetId = o.packetId; lap = o.lap; totalLaps = o.totalLaps; bestLapMs = o.bestLapMs; lastLapMs = o.lastLapMs;
        timeOfDayMs = o.timeOfDayMs; rpmAlertMin = o.rpmAlertMin; rpmAlertMax = o.rpmAlertMax; flags = o.flags;
        gear = o.gear; suggestedGear = o.suggestedGear; throttle = o.throttle; brake = o.brake; clutch = o.clutch;
        carCode = o.carCode;
    }

    // ---- decodificación ----
    private static int i32(byte[] b, int o) {
        return (b[o] & 0xff) | (b[o + 1] & 0xff) << 8 | (b[o + 2] & 0xff) << 16 | (b[o + 3] & 0xff) << 24;
    }
    private static int i16(byte[] b, int o) { return (short) ((b[o] & 0xff) | (b[o + 1] & 0xff) << 8); }
    private static float f32(byte[] b, int o) { return Float.intBitsToFloat(i32(b, o)); }

    /** Descifra el paquete en su lugar y lo decodifica. Devuelve false si no es un paquete válido. */
    boolean decrypt(byte[] p, int len) {
        if (len < PACKET_SIZE) return false;
        boolean b = len >= PACKET_SIZE_B;
        int size = b ? PACKET_SIZE_B : PACKET_SIZE;
        int iv1 = i32(p, 0x40);
        int iv2 = iv1 ^ (b ? IV_XOR_B : IV_XOR);
        byte[] nonce = new byte[8];
        for (int k = 0; k < 4; k++) { nonce[k] = (byte) (iv2 >>> (8 * k)); nonce[4 + k] = (byte) (iv1 >>> (8 * k)); }
        Salsa20.xor(KEY, nonce, p, size);
        if (i32(p, 0) != MAGIC) return false;
        velX = f32(p, 0x10); velY = f32(p, 0x14); velZ = f32(p, 0x18);
        angVelX = f32(p, 0x2C); angVelY = f32(p, 0x30); angVelZ = f32(p, 0x34);
        bodyHeight = f32(p, 0x38);
        for (int k = 0; k < 4; k++) {
            wheelRps[k] = f32(p, 0xA4 + 4 * k); tyreRadius[k] = f32(p, 0xB4 + 4 * k); suspHeight[k] = f32(p, 0xC4 + 4 * k);
        }
        hasSteer = b;
        steer = b ? f32(p, 0x128) : 0;
        posX = f32(p, 0x04); posY = f32(p, 0x08); posZ = f32(p, 0x0C);
        rpm = f32(p, 0x3C);
        fuel = f32(p, 0x44); fuelCapacity = f32(p, 0x48);
        speedMs = f32(p, 0x4C);
        boost = f32(p, 0x50) - 1f;
        oilPressure = f32(p, 0x54); waterTemp = f32(p, 0x58); oilTemp = f32(p, 0x5C);
        for (int k = 0; k < 4; k++) tyreTemp[k] = f32(p, 0x60 + 4 * k);
        packetId = i32(p, 0x70);
        lap = i16(p, 0x74); totalLaps = i16(p, 0x76);
        bestLapMs = i32(p, 0x78); lastLapMs = i32(p, 0x7C);
        timeOfDayMs = i32(p, 0x80);
        rpmAlertMin = i16(p, 0x88) & 0xffff; rpmAlertMax = i16(p, 0x8A) & 0xffff;
        flags = i16(p, 0x8E) & 0xffff;
        gear = p[0x90] & 0x0f; suggestedGear = (p[0x90] >> 4) & 0x0f;
        throttle = p[0x91] & 0xff; brake = p[0x92] & 0xff;
        clutch = f32(p, 0xF4);
        carCode = i32(p, 0x124);
        return true;
    }

    // ---- codificación (sólo para el modo demostración y las pruebas) ----
    private static void w32(byte[] b, int o, int v) { for (int k = 0; k < 4; k++) b[o + k] = (byte) (v >>> (8 * k)); }
    private static void w16(byte[] b, int o, int v) { b[o] = (byte) v; b[o + 1] = (byte) (v >>> 8); }
    private static void wf(byte[] b, int o, float v) { w32(b, o, Float.floatToIntBits(v)); }

    /** Arma un paquete cifrado idéntico al que manda la PS5. */
    byte[] encode(int iv1) { return encode(iv1, false); }

    byte[] encode(int iv1, boolean typeB) {
        int size = typeB ? PACKET_SIZE_B : PACKET_SIZE;
        byte[] p = new byte[size];
        wf(p, 0x10, velX); wf(p, 0x14, velY); wf(p, 0x18, velZ);
        wf(p, 0x2C, angVelX); wf(p, 0x30, angVelY); wf(p, 0x34, angVelZ); wf(p, 0x38, bodyHeight);
        for (int k = 0; k < 4; k++) { wf(p, 0xA4 + 4 * k, wheelRps[k]); wf(p, 0xB4 + 4 * k, tyreRadius[k]); wf(p, 0xC4 + 4 * k, suspHeight[k]); }
        if (typeB) wf(p, 0x128, steer);
        w32(p, 0, MAGIC);
        wf(p, 0x04, posX); wf(p, 0x08, posY); wf(p, 0x0C, posZ);
        wf(p, 0x3C, rpm); wf(p, 0x44, fuel); wf(p, 0x48, fuelCapacity); wf(p, 0x4C, speedMs);
        wf(p, 0x50, boost + 1f); wf(p, 0x54, oilPressure); wf(p, 0x58, waterTemp); wf(p, 0x5C, oilTemp);
        for (int k = 0; k < 4; k++) wf(p, 0x60 + 4 * k, tyreTemp[k]);
        w32(p, 0x70, packetId); w16(p, 0x74, lap); w16(p, 0x76, totalLaps);
        w32(p, 0x78, bestLapMs); w32(p, 0x7C, lastLapMs); w32(p, 0x80, timeOfDayMs);
        w16(p, 0x88, rpmAlertMin); w16(p, 0x8A, rpmAlertMax); w16(p, 0x8E, flags);
        p[0x90] = (byte) ((gear & 0x0f) | (suggestedGear & 0x0f) << 4);
        p[0x91] = (byte) throttle; p[0x92] = (byte) brake;
        wf(p, 0xF4, clutch); w32(p, 0x124, carCode);
        int iv2 = iv1 ^ (typeB ? IV_XOR_B : IV_XOR);
        byte[] nonce = new byte[8];
        for (int k = 0; k < 4; k++) { nonce[k] = (byte) (iv2 >>> (8 * k)); nonce[4 + k] = (byte) (iv1 >>> (8 * k)); }
        Salsa20.xor(KEY, nonce, p, size);
        w32(p, 0x40, iv1); // la PS5 deja el IV en claro en 0x40
        return p;
    }
}
