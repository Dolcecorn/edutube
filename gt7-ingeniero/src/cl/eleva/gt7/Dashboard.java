package cl.eleva.gt7;

import java.util.ArrayList;
import java.util.Locale;

/**
 * Dashboard estilo volante de GT (pantalla negra con cajas de colores, luces de cambio arriba
 * y botones redondos a los lados). Lienzo virtual de 1024x600 (la pantalla de la Iconia B1).
 */
final class Dashboard {
    static final int BG = 0xff000000, BODY = 0xff131417, KNOB = 0xff1b1c21, OFF = 0xff2a2b30,
            WHITE = 0xffffffff, DIM = 0xff8a8f9c, LABEL = 0xffffe34d, GEAR = 0xffffe600,
            YELLOW = 0xffe8d44d, RED = 0xffe5483e, BLUE = 0xff3d7bff, PURPLE = 0xffa071ff,
            TEAL = 0xff2ad4b0, ORANGE = 0xffff8a2a, GREEN = 0xff2fdc6e, SILVER = 0xffc9ccd3;

    // botones: id, etiqueta, color
    static final int B_RAD = 0, B_FUEL = 1, B_TYR = 2, B_LAP = 3, B_VOLDN = 4,
            B_PIT = 5, B_OK = 6, B_MUTE = 7, B_SET = 8, B_VOLUP = 9;
    static final String[] B_LABEL = {"RAD", "FUEL", "TYR", "LAP", "VOL-", "PIT", "OK", "MUTE", "SET", "VOL+"};
    static final int[] B_COLOR = {PURPLE, YELLOW, RED, BLUE, PURPLE, ORANGE, TEAL, YELLOW, BLUE, PURPLE};
    static final float[] B_Y = {132, 224, 316, 408, 500};
    static final float B_R = 37;

    /** Centros de los botones en coordenadas de pantalla (para la vista táctil). */
    final float[] btnX = new float[10], btnY = new float[10];
    float btnR;
    boolean muted, listening;
    int pressed = -1;
    long pressedAt;

    private Painter p;
    private float u, ox, oy;

    private float X(float x) { return ox + x * u; }
    private float Y(float y) { return oy + y * u; }
    private void rect(float l, float t, float r, float b, int c) { p.rect(X(l), Y(t), X(r), Y(b), c); }
    private void round(float l, float t, float r, float b, float rad, int c) { p.round(X(l), Y(t), X(r), Y(b), rad * u, c); }
    private void box(float l, float t, float r, float b, int c) { p.outline(X(l), Y(t), X(r), Y(b), 5 * u, 2.2f * u, c); }
    private void text(String s, float x, float y, float size, int c, int align, boolean bold) { p.text(s, X(x), Y(y), size * u, c, align, bold); }
    private float width(String s, float size, boolean bold) { return p.width(s, size * u, bold) / u; }

    void draw(Painter painter, float w, float h, Telemetry t, Engineer e, String conn, boolean live, long now) {
        p = painter;
        u = Math.min(w / 1024f, h / 600f);
        ox = (w - 1024f * u) / 2f; oy = (h - 600f * u) / 2f;
        p.rect(0, 0, w, h, BG);
        round(4, 2, 1020, 598, 46, BODY);

        drawLights(t, e, now);
        drawWordmark();
        round(110, 94, 914, 568, 12, BG);
        p.outline(X(110), Y(94), X(914), Y(568), 12 * u, 2 * u, 0xff3a3b40);

        drawHeader(t);
        drawEngine(t);
        drawGear(t);
        drawDelta(t, e);
        drawFuel(t, e);
        drawPit(t, e);
        drawTimes(t, e);
        drawTyresRow(t);
        drawEngineer(e, now);
        drawButtons(now);

        text(conn, 512, 590, 13, live ? DIM : ORANGE, Painter.CENTER, false);
        if (!live) drawWaiting(conn);
    }

    // ---- luces de cambio: se encienden desde afuera hacia el centro ----
    private void drawLights(Telemetry t, Engineer e, long now) {
        int max = t.rpmAlertMax > 1000 ? t.rpmAlertMax : 8000;
        int min = t.rpmAlertMin > 0 && t.rpmAlertMin < max ? t.rpmAlertMin : (int) (max * 0.85f);
        float start = Math.max(0, min - (max - min) * 2.5f);
        float frac = (t.rpm - start) / (max - start);
        boolean shift = t.rpm >= max || t.revLimiter();
        boolean flash = (now / 90) % 2 == 0;
        int n = 12;
        for (int i = 0; i < n; i++) {
            int k = Math.min(i, n - 1 - i);          // 0 = extremo, 5 = centro
            int on = k < 2 ? GREEN : k < 4 ? GEAR : RED;
            int c = shift ? (flash ? BLUE : OFF) : (frac >= (k + 1) / 6f ? on : OFF);
            p.circle(X(262 + i * 45.5f), Y(26), 11 * u, c);
        }
        // luces moradas laterales: parpadean cuando el ingeniero habla
        boolean radio = now - e.lastMessageAt < 4000 && (now / 250) % 2 == 0;
        float[][] side = {{214, 38}, {190, 60}, {172, 84}};
        for (float[] d : side) {
            int c = radio ? PURPLE : 0xff3b2c5c;
            p.circle(X(d[0]), Y(d[1]), 9 * u, c);
            p.circle(X(1024 - d[0]), Y(d[1]), 9 * u, c);
        }
    }

    private void drawWordmark() {
        String s = "PORSCHE";
        float size = 30, gap = 14, total = 0;
        for (int i = 0; i < s.length(); i++) total += width(s.substring(i, i + 1), size, true) + (i > 0 ? gap : 0);
        float x = 512 - total / 2;
        for (int i = 0; i < s.length(); i++) {
            String ch = s.substring(i, i + 1);
            text(ch, x, 80, size, SILVER, Painter.LEFT, true);
            x += width(ch, size, true) + gap;
        }
    }

    // ---- fila superior ----
    private void drawHeader(Telemetry t) {
        String lap = t.lap <= 0 ? "--" : t.totalLaps > 0 ? Math.min(t.lap, t.totalLaps) + "/" + t.totalLaps : String.valueOf(t.lap);
        box(120, 102, 280, 138, YELLOW);
        text("Vuelta", 128, 127, 17, WHITE, Painter.LEFT, false);
        text(lap, 272, 128, 21, WHITE, Painter.RIGHT, true);
        if (t.tcs()) round(284, 102, 370, 138, 5, RED);
        box(284, 102, 370, 138, RED);
        text("TCS", 327, 127, 18, t.tcs() ? WHITE : RED, Painter.CENTER, true);

        box(376, 102, 648, 138, BLUE);
        text(String.valueOf(Math.round(t.kmh())), 520, 130, 25, WHITE, Painter.RIGHT, true);
        text("km/h", 528, 130, 15, DIM, Painter.LEFT, false);

        if (t.asm()) round(654, 102, 740, 138, 5, BLUE);
        box(654, 102, 740, 138, BLUE);
        text("ASM", 697, 127, 18, t.asm() ? WHITE : BLUE, Painter.CENTER, true);
        box(744, 102, 904, 138, PURPLE);
        text("rpm", 752, 127, 15, DIM, Painter.LEFT, false);
        text(String.valueOf(Math.round(t.rpm)), 896, 128, 21, WHITE, Painter.RIGHT, true);
    }

    private void kv(String k, String v, float l, float r, float y, float size) {
        text(k, l + 8, y, size, LABEL, Painter.LEFT, false);
        text(v, r - 8, y, size, WHITE, Painter.RIGHT, false);
    }

    private void drawEngine(Telemetry t) {
        box(120, 144, 370, 330, BLUE);
        kv("Temp. aceite", Math.round(t.oilTemp) + "°C", 120, 370, 184, 19);
        kv("Pres. aceite", String.format(Locale.US, "%.2f", t.oilPressure), 120, 370, 224, 19);
        kv("Temp. agua", Math.round(t.waterTemp) + "°C", 120, 370, 264, 19);
        kv("Turbo", t.hasTurbo() ? String.format(Locale.US, "%+.2f bar", t.boost) : "--", 120, 370, 304, 19);
    }

    private void drawGear(Telemetry t) {
        box(376, 144, 648, 330, BLUE);
        String g = t.gear == 0 ? "R" : t.gear == 15 ? "N" : String.valueOf(t.gear);
        if (t.speedMs < 0.5f && t.gear == 0 && t.rpm < 100) g = "-";
        p.emblem(X(384), Y(150), X(436), Y(216));
        text(g, 512, 312, 200, GEAR, Painter.CENTER, true);
        if (t.suggestedGear > 0 && t.suggestedGear < 15 && t.suggestedGear != t.gear)
            text("SUG " + t.suggestedGear, 640, 170, 16, LABEL, Painter.RIGHT, true);
    }

    private void drawDelta(Telemetry t, Engineer e) {
        box(654, 144, 904, 330, BLUE);
        text("Delta", 779, 172, 18, LABEL, Painter.CENTER, true);
        if (e.deltaValid) {
            float d = e.deltaS;
            int c = d <= -0.005f ? GREEN : d >= 0.005f ? RED : WHITE;
            text(String.format(Locale.US, "%+.2f", d), 779, 230, 50, c, Painter.CENTER, false);
        } else text("--.--", 779, 230, 50, DIM, Painter.CENTER, false);
        text("Vuelta actual", 779, 270, 18, LABEL, Painter.CENTER, true);
        text(t.lap > 0 ? Engineer.clockText(e.lapTimeS) : "--:--.---", 779, 312, 34, WHITE, Painter.CENTER, false);
    }

    private void drawFuel(Telemetry t, Engineer e) {
        box(120, 336, 370, 470, YELLOW);
        boolean f = t.hasFuel();
        kv("Combustible", f ? Math.round(t.fuelPct()) + "%" : "--", 120, 370, 366, 19);
        kv("Consumo/v", e.fuelPerLapPct > 0 ? String.format(Locale.US, "%.1f%%", e.fuelPerLapPct) : "--", 120, 370, 398, 19);
        kv("Alcanza", e.fuelLapsLeft >= 0 ? String.format(Locale.US, "%.1f v", e.fuelLapsLeft) : "--", 120, 370, 430, 19);
        kv("Faltan", e.lapsToGo > 0 ? e.lapsToGo + " v" : "--", 120, 370, 462, 19);
        if (f && e.fuelLapsLeft >= 0 && e.lapsToGo > 0 && e.fuelLapsLeft < e.lapsToGo - e.lapFraction())
            text("!", 230, 430, 19, RED, Painter.LEFT, true);
    }

    private void drawPit(Telemetry t, Engineer e) {
        box(376, 336, 648, 470, YELLOW);
        text("CARGAR EN BOXES", 512, 362, 15, WHITE, Painter.CENTER, false);
        float add = e.fuelToAdd(t);
        String v = add < 0 ? "--" : String.valueOf(Math.round(add));
        text(v, 512, 440, 72, add > 0.5f ? WHITE : GREEN, Painter.CENTER, false);
        text("% del estanque", 512, 462, 14, DIM, Painter.CENTER, false);
    }

    private void drawTimes(Telemetry t, Engineer e) {
        box(654, 336, 904, 470, PURPLE);
        int best = t.bestLapMs > 0 ? t.bestLapMs : e.myBestMs;
        text("Última", 662, 362, 17, LABEL, Painter.LEFT, true);
        text(Engineer.msText(t.lastLapMs), 896, 398, 30, WHITE, Painter.RIGHT, false);
        text("Mejor", 662, 424, 17, LABEL, Painter.LEFT, true);
        text(Engineer.msText(best), 896, 460, 30, 0xffc9a6ff, Painter.RIGHT, false);
    }

    static int tyreColor(float c) {
        if (c < 60) return BLUE;
        if (c < 85) return GREEN;
        if (c < 100) return GEAR;
        return RED;
    }

    private void drawTyresRow(Telemetry t) {
        String[] n = {"DI", "DD", "TI", "TD"};
        for (int i = 0; i < 4; i++) {
            float l = 120 + i * 133.5f;
            int c = tyreColor(t.tyreTemp[i]);
            box(l, 476, l + 127.5f, 512, c);
            text(n[i], l + 8, 500, 14, c, Painter.LEFT, true);
            text(Math.round(t.tyreTemp[i]) + "°", l + 119, 502, 20, WHITE, Painter.RIGHT, false);
        }
        // pedales
        box(654, 476, 904, 512, TEAL);
        bar(662, 483, 896, 492, t.throttle / 255f, GREEN);
        bar(662, 497, 896, 506, t.brake / 255f, RED);
    }

    private void bar(float l, float tp, float r, float b, float v, int c) {
        round(l, tp, r, b, 3, OFF);
        v = Math.max(0, Math.min(1, v));
        if (v > 0.01f) round(l, tp, l + (r - l) * v, b, 3, c);
    }

    private void drawEngineer(Engineer e, long now) {
        boolean fresh = now - e.lastMessageAt < 6000;
        box(120, 518, 904, 562, fresh ? LABEL : TEAL);
        String msg = e.lastMessage.length() > 0 ? e.lastMessage : "Ingeniero listo. Toca RAD para preguntarme algo.";
        float size = 17;
        ArrayList<String> lines = wrap(msg, size, 768);
        while (lines.size() > 2 && size > 12) { size -= 1; lines = wrap(msg, size, 768); }
        float y = lines.size() == 1 ? 546 : 537;
        for (int i = 0; i < lines.size() && i < 2; i++, y += size * 1.15f)
            text(lines.get(i), 128, y, size, WHITE, Painter.LEFT, false);
    }

    private void drawButtons(long now) {
        btnR = B_R * u;
        for (int i = 0; i < 10; i++) {
            float cx = i < 5 ? 56 : 968, cy = B_Y[i % 5];
            btnX[i] = X(cx); btnY[i] = Y(cy);
            boolean down = (i == pressed && now - pressedAt < 200) || (i == B_RAD && listening && (now / 300) % 2 == 0);
            int c = B_COLOR[i];
            String label = B_LABEL[i];
            if (i == B_MUTE && muted) { c = RED; label = "VOZ"; }
            p.circle(X(cx), Y(cy), (B_R + 4) * u, 0xff0b0b0d);
            p.circle(X(cx), Y(cy), B_R * u, down ? c : KNOB);
            p.ring(X(cx), Y(cy), (B_R - 3) * u, 5 * u, c);
            text(label, cx, cy + 6, label.length() > 3 ? 15 : 18, down ? BG : c == BLUE ? 0xff8fb3ff : c, Painter.CENTER, true);
        }
    }

    private ArrayList<String> wrap(String s, float size, float maxW) {
        ArrayList<String> out = new ArrayList<String>();
        StringBuilder line = new StringBuilder();
        for (String w : s.split(" ")) {
            String cand = line.length() == 0 ? w : line + " " + w;
            if (width(cand, size, false) > maxW && line.length() > 0) { out.add(line.toString()); line = new StringBuilder(w); }
            else line = new StringBuilder(cand);
        }
        if (line.length() > 0) out.add(line.toString());
        return out;
    }

    private void drawWaiting(String conn) {
        round(150, 150, 874, 470, 14, 0xff050505);
        box(150, 150, 874, 470, YELLOW);
        text("Esperando datos de Gran Turismo 7", 512, 208, 30, LABEL, Painter.CENTER, true);
        text(conn, 512, 250, 19, ORANGE, Painter.CENTER, false);
        text("1. La PS5 y la tablet deben estar en el mismo wifi.", 186, 306, 19, WHITE, Painter.LEFT, false);
        text("2. En GT7 entra a una carrera o prueba de manejo.", 186, 340, 19, WHITE, Painter.LEFT, false);
        text("3. Si no conecta, escribe la IP de la PS5 en SET.", 186, 374, 19, WHITE, Painter.LEFT, false);
        text("(PS5: Ajustes > Red > Estado de la conexión)", 186, 408, 16, DIM, Painter.LEFT, false);
        text("Botón SET: ajustes y modo demostración", 186, 442, 16, DIM, Painter.LEFT, false);
    }
}
