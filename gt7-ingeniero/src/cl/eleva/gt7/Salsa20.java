package cl.eleva.gt7;

/** Salsa20/20 mínimo (clave 32 bytes, nonce 8 bytes), usado por la telemetría de GT7. */
final class Salsa20 {
    private Salsa20() {}

    private static int rotl(int v, int c) { return (v << c) | (v >>> (32 - c)); }

    private static int le(byte[] b, int o) {
        return (b[o] & 0xff) | (b[o + 1] & 0xff) << 8 | (b[o + 2] & 0xff) << 16 | (b[o + 3] & 0xff) << 24;
    }

    /** Cifra o descifra data[0..len) en el mismo arreglo (XOR con el flujo de clave). */
    static void xor(byte[] key, byte[] nonce, byte[] data, int len) {
        int[] s = new int[16];
        int[] x = new int[16];
        s[0] = 0x61707865; s[5] = 0x3320646e; s[10] = 0x79622d32; s[15] = 0x6b206574;
        for (int i = 0; i < 4; i++) { s[1 + i] = le(key, i * 4); s[11 + i] = le(key, 16 + i * 4); }
        s[6] = le(nonce, 0); s[7] = le(nonce, 4);
        long counter = 0;
        for (int off = 0; off < len; off += 64, counter++) {
            s[8] = (int) counter; s[9] = (int) (counter >>> 32);
            System.arraycopy(s, 0, x, 0, 16);
            for (int r = 0; r < 10; r++) {
                x[4] ^= rotl(x[0] + x[12], 7);   x[8] ^= rotl(x[4] + x[0], 9);
                x[12] ^= rotl(x[8] + x[4], 13);  x[0] ^= rotl(x[12] + x[8], 18);
                x[9] ^= rotl(x[5] + x[1], 7);    x[13] ^= rotl(x[9] + x[5], 9);
                x[1] ^= rotl(x[13] + x[9], 13);  x[5] ^= rotl(x[1] + x[13], 18);
                x[14] ^= rotl(x[10] + x[6], 7);  x[2] ^= rotl(x[14] + x[10], 9);
                x[6] ^= rotl(x[2] + x[14], 13);  x[10] ^= rotl(x[6] + x[2], 18);
                x[3] ^= rotl(x[15] + x[11], 7);  x[7] ^= rotl(x[3] + x[15], 9);
                x[11] ^= rotl(x[7] + x[3], 13);  x[15] ^= rotl(x[11] + x[7], 18);
                x[1] ^= rotl(x[0] + x[3], 7);    x[2] ^= rotl(x[1] + x[0], 9);
                x[3] ^= rotl(x[2] + x[1], 13);   x[0] ^= rotl(x[3] + x[2], 18);
                x[6] ^= rotl(x[5] + x[4], 7);    x[7] ^= rotl(x[6] + x[5], 9);
                x[4] ^= rotl(x[7] + x[6], 13);   x[5] ^= rotl(x[4] + x[7], 18);
                x[11] ^= rotl(x[10] + x[9], 7);  x[8] ^= rotl(x[11] + x[10], 9);
                x[9] ^= rotl(x[8] + x[11], 13);  x[10] ^= rotl(x[9] + x[8], 18);
                x[12] ^= rotl(x[15] + x[14], 7); x[13] ^= rotl(x[12] + x[15], 9);
                x[14] ^= rotl(x[13] + x[12], 13); x[15] ^= rotl(x[14] + x[13], 18);
            }
            for (int i = 0; i < 16; i++) {
                int v = x[i] + s[i];
                for (int k = 0; k < 4; k++) {
                    int p = off + i * 4 + k;
                    if (p < len) data[p] ^= (byte) (v >>> (8 * k));
                }
            }
        }
    }
}
