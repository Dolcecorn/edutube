package cl.eleva.gt7;

import java.util.ArrayList;
import java.util.Locale;

/** Dibuja el dashboard en un lienzo virtual de 1024x600 (la pantalla de la Iconia B1). */
final class Dashboard {
    static final int BG = 0xff0a0c10, PANEL = 0xff161b24, PANEL2 = 0xff1e2430, TXT = 0xffffffff,
            DIM = 0xff8a93a6, GREEN = 0xff2ecc71, YELLOW = 0xfff1c40f, RED = 0xffe74c3c, BLUE = 0xff3498db,
            ORANGE = 0xffe67e22, CYAN = 0xff1abc9c;

    // zonas táctiles (en coordenadas de pantalla), las usa la vista
    float menuL, menuT, menuR, menuB, engL, engT, engR, engB;

    private Painter p;
    private float u, ox, oy;

    private float X(float x) { return ox + x * u; }
    private float Y(float y) { return oy + y * u; }
    private void rect(float l, float t, float r, float b, int c) { p.rect(X(l), Y(t), X(r), Y(b), c); }
    private void round(float l, float t, float r, float b, float rad, int c) { p.round(X(l), Y(t), X(r), Y(b), rad * u, c); }
    private void text(String s, float x, float y, float size, int c, int align, boolean bold) { p.text(s, X(x), Y(y), size * u, c, align, bold); }
    private float width(String s, float size, boolean bold) { return p.width(s, size * u, bold) / u; }

    /**
     * @param conn texto de conexión ("Conectado a 192.168.1.20", "Buscando PS5...")
     * @param live true si llegaron datos en los últimos 2 s
     */
    void draw(Painter painter, float w, float h, Telemetry t, Engineer e, String conn, boolean live, long nowMs) {
        p = painter;
        u = Math.min(w / 1024f, h / 600f);
        ox = (w - 1024f * u) / 2f; oy = (h - 600f * u) / 2f;
        p.rect(0, 0, w, h, BG);

        drawRevBar(t, nowMs);
        drawTimes(t, e);
        drawCenter(t);
        drawFuel(t, e);
        drawTyres(t);
        drawPedals(t);
        drawEngineer(e);

        text(conn, 12, 76, 15, live ? GREEN : ORANGE, Painter.LEFT, false);
        if (!live) drawWaiting(conn);
        round(904, 58, 1016, 94, 8, live ? PANEL2 : BLUE);
        text("AJUSTES", 960, 82, 16, TXT, Painter.CENTER, true);
        menuL = X(880); menuT = Y(48); menuR = X(1024); menuB = Y(100);
    }

    private void drawRevBar(Telemetry t, long now) {
        int max = t.rpmAlertMax > 1000 ? t.rpmAlertMax : 8000;
        int min = t.rpmAlertMin > 0 && t.rpmAlertMin < max ? t.rpmAlertMin : (int) (max * 0.85f);
        float start = Math.max(0, min - (max - min) * 3f);  // la barra empieza a encender antes de la alerta
        int n = 20;
        boolean shift = t.rpm >= max || t.revLimiter();
        boolean flashOn = (now / 90) % 2 == 0;
        float segW = (1024f - 16 - (n - 1) * 4) / n;
        for (int i = 0; i < n; i++) {
            float l = 8 + i * (segW + 4);
            float thr = start + (max - start) * (i + 1) / (float) n;
            int on;
            if (i < n * 0.6f) on = GREEN; else if (i < n * 0.85f) on = YELLOW; else on = RED;
            int c = shift ? (flashOn ? BLUE : PANEL) : (t.rpm >= thr ? on : PANEL);
            round(l, 6, l + segW, 44, 5, c);
        }
    }

    private void drawTimes(Telemetry t, Engineer e) {
        round(8, 100, 330, 400, 12, PANEL);
        String lap = t.lap <= 0 ? "--" : t.totalLaps > 0 ? Math.min(t.lap, t.totalLaps) + "/" + t.totalLaps : String.valueOf(t.lap);
        text("VUELTA", 24, 128, 16, DIM, Painter.LEFT, true);
        text(lap, 314, 136, 40, TXT, Painter.RIGHT, true);

        row("ACTUAL", t.lap > 0 ? Engineer.clockText(e.lapTimeS) : "--:--.---", 186, TXT);
        row("ÚLTIMA", Engineer.msText(t.lastLapMs), 230, TXT);
        int best = t.bestLapMs > 0 ? t.bestLapMs : e.myBestMs;
        row("MEJOR", Engineer.msText(best), 274, 0xffb388ff);

        text("DELTA", 24, 318, 16, DIM, Painter.LEFT, true);
        if (e.deltaValid) {
            float d = e.deltaS;
            int c = d <= -0.005f ? GREEN : d >= 0.005f ? RED : TXT;
            round(18, 326, 320, 390, 10, d <= 0 ? 0xff123d27 : 0xff4a1a17);
            text(String.format(Locale.US, "%+.2f", d), 169, 378, 54, c, Painter.CENTER, true);
        } else {
            text("--.--", 169, 378, 54, DIM, Painter.CENTER, true);
        }
    }

    private void row(String label, String value, float y, int c) {
        text(label, 24, y, 16, DIM, Painter.LEFT, true);
        text(value, 314, y + 4, 34, c, Painter.RIGHT, true);
    }

    private void drawCenter(Telemetry t) {
        round(340, 100, 684, 400, 12, PANEL);
        String g = t.gear == 0 ? "R" : t.gear == 15 ? "N" : String.valueOf(t.gear);
        if (t.speedMs < 0.5f && t.gear == 0 && t.rpm < 100) g = "-";
        text(g, 512, 300, 210, TXT, Painter.CENTER, true);
        if (t.suggestedGear > 0 && t.suggestedGear < 15 && t.suggestedGear != t.gear)
            text("SUG " + t.suggestedGear, 664, 138, 22, YELLOW, Painter.RIGHT, true);
        text(String.valueOf(Math.round(t.kmh())), 500, 380, 64, TXT, Painter.RIGHT, true);
        text("km/h", 508, 380, 22, DIM, Painter.LEFT, false);
        text(Math.round(t.rpm) + " rpm", 360, 138, 20, DIM, Painter.LEFT, false);
        // asistencias
        float ax = 360;
        if (t.tcs()) { badge("TCS", ax, ORANGE); ax += 70; }
        if (t.asm()) { badge("ASM", ax, ORANGE); }
    }

    private void badge(String s, float x, int c) {
        round(x, 150, x + 62, 178, 6, c);
        text(s, x + 31, 171, 17, BG, Painter.CENTER, true);
    }

    private void drawFuel(Telemetry t, Engineer e) {
        round(694, 100, 1016, 236, 12, PANEL);
        text("COMBUSTIBLE", 710, 128, 16, DIM, Painter.LEFT, true);
        if (!t.hasFuel()) {
            text("sin datos", 1000, 132, 24, DIM, Painter.RIGHT, true);
            return;
        }
        float pct = Math.max(0, Math.min(100, t.fuelPct()));
        text(Math.round(pct) + "%", 1000, 134, 32, TXT, Painter.RIGHT, true);
        int fc = e.fuelLapsLeft >= 0 && e.lapsToGo > 0 && e.fuelLapsLeft < e.lapsToGo - e.lapFraction() ? RED
                : pct < 15 ? ORANGE : GREEN;
        round(710, 146, 1000, 170, 6, PANEL2);
        if (pct > 0) round(710, 146, 710 + 290 * pct / 100f, 170, 6, fc);
        String laps = e.fuelLapsLeft >= 0 ? "Alcanza " + String.format(Locale.US, "%.1f", e.fuelLapsLeft) + " v" : "Midiendo consumo…";
        text(laps, 710, 200, 22, e.fuelLapsLeft >= 0 ? fc : DIM, Painter.LEFT, true);
        if (e.lapsToGo > 0) text("Faltan " + e.lapsToGo, 1000, 200, 22, TXT, Painter.RIGHT, true);
        if (e.fuelPerLapPct > 0)
            text(String.format(Locale.US, "Consumo %.1f%% por vuelta", e.fuelPerLapPct), 710, 226, 16, DIM, Painter.LEFT, false);
    }

    static int tyreColor(float c) {
        if (c < 60) return BLUE;
        if (c < 85) return GREEN;
        if (c < 100) return YELLOW;
        return RED;
    }

    private void drawTyres(Telemetry t) {
        round(694, 246, 1016, 400, 12, PANEL);
        text("NEUMÁTICOS °C", 710, 272, 16, DIM, Painter.LEFT, true);
        float[] xs = {710, 862};
        float[] ys = {282, 340};
        for (int i = 0; i < 4; i++) {
            float l = xs[i % 2], tp = ys[i / 2];
            float c = t.tyreTemp[i];
            round(l, tp, l + 138, tp + 50, 8, tyreColor(c));
            text(String.valueOf(Math.round(c)), l + 69, tp + 38, 34, BG, Painter.CENTER, true);
        }
    }

    private void drawPedals(Telemetry t) {
        round(8, 410, 1016, 466, 12, PANEL);
        text("ACEL", 22, 444, 16, DIM, Painter.LEFT, true);
        bar(78, 424, 410, 452, t.throttle / 255f, GREEN);
        text("FRENO", 428, 444, 16, DIM, Painter.LEFT, true);
        bar(492, 424, 690, 452, t.brake / 255f, RED);
        String extra = "Agua " + Math.round(t.waterTemp) + "°  Aceite " + Math.round(t.oilTemp) + "°";
        if (t.hasTurbo()) extra += String.format(Locale.US, "  Turbo %.2f", t.boost);
        text(extra, 1004, 444, 16, DIM, Painter.RIGHT, false);
    }

    private void bar(float l, float tp, float r, float b, float v, int c) {
        round(l, tp, r, b, 6, PANEL2);
        v = Math.max(0, Math.min(1, v));
        if (v > 0.01f) round(l, tp, l + (r - l) * v, b, 6, c);
    }

    private void drawEngineer(Engineer e) {
        round(8, 476, 1016, 594, 12, 0xff10202a);
        text("INGENIERO", 24, 502, 16, CYAN, Painter.LEFT, true);
        text("toca aquí para pedir el estado", 1000, 502, 14, DIM, Painter.RIGHT, false);
        String msg = e.lastMessage.length() > 0 ? e.lastMessage : "Listo. Te hablo al cerrar cada vuelta.";
        float size = 24;
        ArrayList<String> lines = wrap(msg, size, 970);
        while (lines.size() > 3 && size > 14) { size -= 2; lines = wrap(msg, size, 970); }
        float y = 534;
        for (int i = 0; i < lines.size() && i < 3; i++, y += size * 1.25f)
            text(lines.get(i), 24, y, size, TXT, Painter.LEFT, false);
        engL = X(8); engT = Y(476); engR = X(1016); engB = Y(594);
    }

    private ArrayList<String> wrap(String s, float size, float maxW) {
        ArrayList<String> out = new ArrayList<String>();
        String[] words = s.split(" ");
        StringBuilder line = new StringBuilder();
        for (String w : words) {
            String cand = line.length() == 0 ? w : line + " " + w;
            if (width(cand, size, false) > maxW && line.length() > 0) {
                out.add(line.toString());
                line = new StringBuilder(w);
            } else {
                line = new StringBuilder(cand);
            }
        }
        if (line.length() > 0) out.add(line.toString());
        return out;
    }

    private void drawWaiting(String conn) {
        rect(0, 0, 1024, 600, 0xd0000000);
        round(152, 150, 872, 450, 16, PANEL);
        text("Esperando datos de Gran Turismo 7", 512, 210, 32, TXT, Painter.CENTER, true);
        text(conn, 512, 254, 20, ORANGE, Painter.CENTER, false);
        text("1. La PS5 y la tablet deben estar en el mismo wifi.", 190, 310, 20, DIM, Painter.LEFT, false);
        text("2. En GT7 entra a una carrera o prueba de manejo.", 190, 344, 20, DIM, Painter.LEFT, false);
        text("3. Si no conecta, escribe la IP de la PS5 en AJUSTES.", 190, 378, 20, DIM, Painter.LEFT, false);
        text("(PS5: Ajustes > Red > Estado de la conexión)", 190, 412, 17, DIM, Painter.LEFT, false);
    }
}
