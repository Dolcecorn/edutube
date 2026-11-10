package cl.eleva.gt7;

import java.util.ArrayList;
import java.util.Locale;

/**
 * Pantalla de análisis (se abre deslizando a la izquierda y sola al terminar la carrera):
 * resumen, mapa del circuito, curvas, vueltas y dinámica del auto.
 */
final class Analysis {
    static final String[] TABS = {"RESUMEN", "MAPA", "CURVAS", "VUELTAS", "AUTO"};
    static final int PANEL = 0xe0000000, GRID = 0xff2a2b30;

    int tab;
    // zonas táctiles en pantalla
    final float[] tabL = new float[TABS.length], tabR = new float[TABS.length];
    float tabT, tabB, backL, backR;
    String csvPath = "";

    private Painter p;
    private float u, sx, sy;

    private float X(float x) { return x * sx; }
    private float Y(float y) { return y * sy; }
    private void round(float l, float t, float r, float b, float rad, int c) { p.round(X(l), Y(t), X(r), Y(b), rad * u, c); }
    private void box(float l, float t, float r, float b, int c) { p.outline(X(l), Y(t), X(r), Y(b), 6 * u, 2f * u, c); }
    private void text(String s, float x, float y, float size, int c, int align, boolean bold) { p.text(s, X(x), Y(y), size * u, c, align, bold); }
    private float width(String s, float size, boolean bold) { return p.width(s, size * u, bold) / sx; }
    private void line(float x1, float y1, float x2, float y2, float w, int c) { p.line(X(x1), Y(y1), X(x2), Y(y2), w * u, c); }

    void draw(Painter painter, float w, float h, Telemetry t, Engineer e, long now) {
        p = painter;
        sx = w / 1024f; sy = h / 600f; u = Math.min(sx, sy);
        p.carbon(0, 0, w, h);

        // barra superior
        round(10, 10, 168, 54, 10, Dashboard.KNOB);
        box(10, 10, 168, 54, Dashboard.TEAL);
        text("< VOLANTE", 89, 39, 17, Dashboard.TEAL, Painter.CENTER, true);
        backL = X(0); backR = X(178);
        float tw = (1014 - 182) / (float) TABS.length;
        for (int i = 0; i < TABS.length; i++) {
            float l = 182 + i * tw, r = l + tw - 8;
            boolean sel = i == tab;
            round(l, 10, r, 54, 10, sel ? Dashboard.LABEL : Dashboard.KNOB);
            if (!sel) box(l, 10, r, 54, Dashboard.YELLOW);
            text(TABS[i], (l + r) / 2, 39, 17, sel ? Dashboard.BG : Dashboard.LABEL, Painter.CENTER, true);
            tabL[i] = X(l); tabR[i] = X(r);
        }
        tabT = Y(0); tabB = Y(64);
        round(10, 66, 1014, 592, 12, PANEL);

        switch (tab) {
            case 0: drawSummary(t, e); break;
            case 1: drawMap(t, e); break;
            case 2: drawCorners(e); break;
            case 3: drawLaps(e); break;
            default: drawCar(t, e); break;
        }
    }

    // ---------------------------------------------------------------- RESUMEN
    private void drawSummary(Telemetry t, Engineer e) {
        Session s = e.session;
        Session.Lap b = s.best();
        tile(24, 80, 330, 170, "MEJOR VUELTA", b != null ? Engineer.msText(b.ms) : "--:--.---",
                b != null ? "vuelta " + b.lap : "", 0xffc9a6ff);
        int ideal = s.idealMs();
        tile(24, 180, 330, 270, "VUELTA IDEAL", ideal > 0 ? Engineer.msText(ideal) : "--:--.---",
                ideal > 0 && b != null ? String.format(Locale.US, "mejores sectores: %.2f s menos", Math.max(0, b.ms - ideal) / 1000f)
                        : "mejores 3 sectores", Dashboard.GREEN);
        float cons = s.consistency();
        tile(24, 280, 330, 370, "CONSISTENCIA", cons >= 0 ? String.format(Locale.US, "±%.2f s", cons) : "--",
                cons < 0 ? "necesito 3 vueltas" : cons < 0.4f ? "muy constante" : cons < 1f ? "bien" : "irregular", Dashboard.WHITE);
        tile(24, 380, 330, 470, "VELOCIDAD MÁXIMA", s.topKmh > 0 ? Math.round(s.topKmh) + " km/h" : "--", "", Dashboard.WHITE);
        tile(24, 480, 330, 578, "FUERZA G MÁXIMA", String.format(Locale.US, "%.1f  /  %.1f", e.dyn.maxGLat, e.dyn.maxGBrake),
                "curva  /  frenada", Dashboard.WHITE);

        String[] names = {"BLOQUEOS", "PATINAJES", "SOBREVIRAJE", "SUBVIRAJE"};
        int[] colors = {Dashboard.ORANGE, Dashboard.PURPLE, Dashboard.RED, Dashboard.BLUE};
        for (int i = 0; i < 4; i++) {
            float l = 344 + i * 166;
            round(l, 80, l + 158, 170, 10, 0xff101114);
            box(l, 80, l + 158, 170, colors[i]);
            text(names[i], l + 79, 104, 14, colors[i], Painter.CENTER, true);
            text(String.valueOf(s.count(i)), l + 79, 154, 42, Dashboard.WHITE, Painter.CENTER, true);
        }
        box(344, 180, 1000, 578, Dashboard.TEAL);
        String head = e.debriefList.size() > 0 ? "RESUMEN DEL INGENIERO"
                : e.debriefPending() ? "EL RESUMEN SALE EN UNOS SEGUNDOS" : "EN VIVO (el resumen completo sale al terminar la carrera)";
        text(head, 360, 206, 15, Dashboard.TEAL, Painter.LEFT, true);
        if (s.trackName.length() > 0) text(s.trackName.toUpperCase(Locale.US), 988, 206, 15, Dashboard.YELLOW, Painter.RIGHT, true);
        if (e.debriefList.size() > 0) bullets(e.debriefList, 360, 238, 628, 562, 18);
        else paragraph(liveSummary(s), 360, 236, 640, 570, 19);
        if (csvPath.length() > 0) text("Datos guardados en " + csvPath, 990, 572, 12, Dashboard.DIM, Painter.RIGHT, false);
    }

    private String liveSummary(Session s) {
        if (s.laps.isEmpty()) return "Todavía no hay vueltas completas. Desliza a la derecha para volver al volante.";
        StringBuilder sb = new StringBuilder();
        int[] worst = s.worstCorners(3);
        if (worst.length > 0) {
            sb.append("Donde más pierdes hasta ahora: ");
            for (int k = 0; k < worst.length; k++)
                sb.append(k > 0 ? ", " : "").append("curva ").append(worst[k] + 1)
                  .append(String.format(Locale.US, " (%.2f s)", s.avgLoss(worst[k])));
            sb.append(". ");
        }
        sb.append("Vueltas completas: ").append(s.laps.size()).append(".");
        return sb.toString();
    }

    private void tile(float l, float tp, float r, float b, String label, String value, String sub, int c) {
        round(l, tp, r, b, 10, 0xff101114);
        box(l, tp, r, b, Dashboard.YELLOW);
        text(label, l + 14, tp + 24, 14, Dashboard.LABEL, Painter.LEFT, true);
        text(value, r - 14, tp + 66, 32, c, Painter.RIGHT, false);
        if (sub.length() > 0) text(sub, l + 14, b - 12, 13, Dashboard.DIM, Painter.LEFT, false);
    }

    private void paragraph(String s, float l, float top, float maxW, float bottom, float size) {
        ArrayList<String> lines = wrap(s, size, maxW);
        while (lines.size() * size * 1.3f > bottom - top && size > 12) { size -= 1; lines = wrap(s, size, maxW); }
        float y = top;
        for (String ln : lines) { if (y > bottom) break; text(ln, l, y, size, Dashboard.WHITE, Painter.LEFT, false); y += size * 1.3f; }
    }

    /** Lista con viñetas; achica la letra hasta que quepa. */
    private void bullets(java.util.List<String> items, float l, float top, float maxW, float bottom, float size) {
        ArrayList<ArrayList<String>> w = new ArrayList<ArrayList<String>>();
        for (;;) {
            w.clear();
            int lines = 0;
            for (String it : items) { ArrayList<String> x = wrap(it, size, maxW - 24); w.add(x); lines += x.size(); }
            if (lines * size * 1.25f + items.size() * size * 0.35f <= bottom - top || size <= 11) break;
            size -= 1;
        }
        float y = top;
        for (int i = 0; i < w.size(); i++) {
            if (y > bottom) break;
            text("•", l + 4, y, size, Dashboard.YELLOW, Painter.LEFT, true);
            for (String ln : w.get(i)) { text(ln, l + 24, y, size, Dashboard.WHITE, Painter.LEFT, false); y += size * 1.25f; }
            y += size * 0.35f;
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

    // ---------------------------------------------------------------- MAPA
    private static int speedColor(float kmh, float lo, float hi) {
        float f = hi > lo ? (kmh - lo) / (hi - lo) : 0.5f;
        if (f < 0.33f) return Dashboard.RED;
        if (f < 0.55f) return Dashboard.ORANGE;
        if (f < 0.78f) return Dashboard.GEAR;
        return Dashboard.GREEN;
    }

    private void drawMap(Telemetry t, Engineer e) {
        Coach.Trace r = e.coach.ref;
        if (r == null || r.n < 50) {
            text("Completa una vuelta para dibujar el mapa del circuito.", 512, 320, 22, Dashboard.DIM, Painter.CENTER, false);
            return;
        }
        float minX = Float.MAX_VALUE, maxX = -Float.MAX_VALUE, minZ = Float.MAX_VALUE, maxZ = -Float.MAX_VALUE, lo = 999, hi = 0;
        for (int i = 0; i < r.n; i++) {
            minX = Math.min(minX, r.x[i]); maxX = Math.max(maxX, r.x[i]); minZ = Math.min(minZ, r.z[i]); maxZ = Math.max(maxZ, r.z[i]);
            lo = Math.min(lo, r.v[i]); hi = Math.max(hi, r.v[i]);
        }
        // área del mapa en coordenadas virtuales, respetando proporción en pantalla
        float l = 30, tp = 84, rr = 740, bb = 580;
        float scale = Math.min((rr - l) * sx / Math.max(1, maxX - minX), (bb - tp) * sy / Math.max(1, maxZ - minZ));
        float offX = X(l) + ((rr - l) * sx - (maxX - minX) * scale) / 2, offY = Y(tp) + ((bb - tp) * sy - (maxZ - minZ) * scale) / 2;
        int step = Math.max(1, r.n / 600);
        float px = offX + (r.x[0] - minX) * scale, py = offY + (r.z[0] - minZ) * scale;
        for (int i = step; i < r.n; i += step) {
            float qx = offX + (r.x[i] - minX) * scale, qy = offY + (r.z[i] - minZ) * scale;
            p.line(px, py, qx, qy, 7 * u, speedColor(r.v[i], lo, hi));
            px = qx; py = qy;
        }
        // eventos de la carrera
        int[] evColor = {Dashboard.ORANGE, Dashboard.PURPLE, Dashboard.RED, Dashboard.BLUE};
        for (Session.Event ev : e.session.events)
            p.circle(offX + (ev.x - minX) * scale, offY + (ev.z - minZ) * scale, 5 * u, evColor[ev.type]);
        // números de curva
        Coach c = e.coach;
        float[] lx0 = new float[c.nc], ly0 = new float[c.nc];
        for (int k = 0; k < c.nc; k++) {
            int a = c.cApex[k];
            float cx = offX + (r.x[a] - minX) * scale, cy = offY + (r.z[a] - minZ) * scale;
            for (int q = 0; q < k; q++)   // no encimar números de curvas muy juntas (chicanas)
                if (Math.abs(lx0[q] - cx) < 28 * u && Math.abs(ly0[q] - cy) < 28 * u) cy -= 30 * u;
            lx0[k] = cx; ly0[k] = cy;
            p.circle(cx, cy, 13 * u, 0xff101114);
            p.ring(cx, cy, 13 * u, 2 * u, Dashboard.WHITE);
            p.text(String.valueOf(k + 1), cx, cy + 6 * u, 15 * u, Dashboard.WHITE, Painter.CENTER, true);
        }
        // límites de sector (tercios de la vuelta)
        float len = r.d[r.n - 1];
        for (int k = 1; k <= 2; k++) {
            int j = 0;
            while (j < r.n - 1 && r.d[j] < len * k / 3f) j++;
            float sxp = offX + (r.x[j] - minX) * scale, syp = offY + (r.z[j] - minZ) * scale;
            p.round(sxp - 17 * u, syp - 11 * u, sxp + 17 * u, syp + 11 * u, 5 * u, Dashboard.YELLOW);
            p.text("S" + (k + 1), sxp, syp + 6 * u, 14 * u, Dashboard.BG, Painter.CENTER, true);
        }
        // meta
        p.circle(offX + (r.x[0] - minX) * scale, offY + (r.z[0] - minZ) * scale, 7 * u, Dashboard.WHITE);
        // auto en vivo
        p.circle(offX + (t.posX - minX) * scale, offY + (t.posZ - minZ) * scale, 9 * u, Dashboard.CYAN_DOT);
        p.ring(offX + (t.posX - minX) * scale, offY + (t.posZ - minZ) * scale, 9 * u, 2 * u, Dashboard.BG);

        // leyenda
        float lx = 760;
        text("VELOCIDAD (mejor vuelta)", lx, 104, 14, Dashboard.LABEL, Painter.LEFT, true);
        String[] sp = {"lenta", "media", "rápida", "a fondo"};
        int[] sc = {Dashboard.RED, Dashboard.ORANGE, Dashboard.GEAR, Dashboard.GREEN};
        for (int i = 0; i < 4; i++) { line(lx, 128 + i * 26, lx + 40, 128 + i * 26, 7, sc[i]); text(sp[i], lx + 52, 134 + i * 26, 15, Dashboard.WHITE, Painter.LEFT, false); }
        text("EVENTOS", lx, 250, 14, Dashboard.LABEL, Painter.LEFT, true);
        String[] en = {"bloqueo", "patinaje", "sobreviraje", "subviraje"};
        for (int i = 0; i < 4; i++) {
            p.circle(X(lx + 8), Y(272 + i * 26), 6 * u, evColor[i]);
            text(en[i] + " (" + e.session.count(i) + ")", lx + 24, 278 + i * 26, 15, Dashboard.WHITE, Painter.LEFT, false);
        }
        text("Punto celeste: tu auto ahora", lx, 400, 14, Dashboard.DIM, Painter.LEFT, false);
        text("Punto blanco: meta", lx, 422, 14, Dashboard.DIM, Painter.LEFT, false);
        text("Curvas: " + c.nc + " (numeradas desde la meta)", lx, 444, 14, Dashboard.DIM, Painter.LEFT, false);
        text("Amarillo: inicio de sector 2 y 3", lx, 466, 14, Dashboard.DIM, Painter.LEFT, false);
        if (e.track != null) {
            text("CIRCUITO", lx, 504, 14, Dashboard.LABEL, Painter.LEFT, true);
            // el nombre puede ser largo: se achica y, si no cabe, va en dos líneas
            String nm = e.track.label();
            float fs = 19, maxW = 1000 - lx;
            String l1 = nm, l2 = null;
            if (width(nm, fs, true) > maxW) {
                int k = nm.indexOf(" - ");
                if (k < 0) { k = nm.lastIndexOf(' ', nm.length() / 2 + 6); }
                if (k > 0) { l1 = nm.substring(0, k).trim(); l2 = nm.substring(k).replaceFirst("^\\s*-?\\s*", ""); }
                while (fs > 12 && (width(l1, fs, true) > maxW || (l2 != null && width(l2, fs, true) > maxW))) fs -= 1;
            }
            text(l1, lx, 528, fs, Dashboard.YELLOW, Painter.LEFT, true);
            if (l2 != null) text(l2, lx, 528 + fs * 1.2f, fs, Dashboard.YELLOW, Painter.LEFT, true);
            if (e.track.builtin) text(e.coach.nc + " curvas (oficial: " + e.track.turns + ")", lx, 578, 13, Dashboard.DIM, Painter.LEFT, false);
            else if (e.track.name.length() == 0) text("ponle nombre en SET", lx, 556, 13, Dashboard.DIM, Painter.LEFT, false);
        }
    }

    // ---------------------------------------------------------------- CURVAS
    private void drawCorners(Engineer e) {
        Session s = e.session;
        if (s.corners == 0) { text("Las curvas aparecen desde la 2ª vuelta.", 512, 320, 22, Dashboard.DIM, Painter.CENTER, false); return; }
        String[] head = {"CURVA", "PIERDES / VUELTA", "V. MÍN MEJOR", "V. MÍN ÚLTIMA", "BLOQ", "PATIN", "SOBRE", "SUBV"};
        float[] col = {40, 150, 470, 600, 720, 795, 870, 945};
        for (int i = 0; i < head.length; i++) text(head[i], col[i], 96, 13, Dashboard.LABEL, i == 1 || i == 0 ? Painter.LEFT : Painter.CENTER, true);
        int n = Math.min(s.corners, Session.MAXC);
        float rowH = Math.min(30, (570 - 108) / (float) n);
        float fs = Math.min(18, rowH * 0.62f);
        int[] worst = s.worstCorners(3);
        float maxLoss = 0.3f;
        for (int c = 0; c < n; c++) maxLoss = Math.max(maxLoss, s.avgLoss(c));
        for (int c = 0; c < n; c++) {
            float y = 108 + c * rowH;
            boolean bad = false;
            for (int w : worst) if (w == c) bad = true;
            if (c % 2 == 0) round(24, y, 1000, y + rowH - 2, 4, 0x14ffffff);
            float yb = y + rowH * 0.7f;
            text(String.valueOf(c + 1), 52, yb, fs, bad ? Dashboard.RED : Dashboard.WHITE, Painter.LEFT, true);
            float loss = s.avgLoss(c);
            float bw = 200 * Math.max(0, loss) / maxLoss;
            round(150, y + rowH * 0.25f, 150 + Math.max(2, bw), y + rowH * 0.75f, 3, loss > 0.1f ? Dashboard.RED : loss > 0.03f ? Dashboard.ORANGE : Dashboard.GREEN);
            text(s.lossN[c] > 0 ? String.format(Locale.US, "%.2f s", loss) : "--", 360, yb, fs, Dashboard.WHITE, Painter.LEFT, false);
            text(s.bestMinV[c] > 0 ? String.valueOf(Math.round(s.bestMinV[c])) : "--", col[2], yb, fs, Dashboard.WHITE, Painter.CENTER, false);
            int dv = Math.round(s.lastMinV[c] - s.bestMinV[c]);
            text(s.lastMinV[c] > 0 ? Math.round(s.lastMinV[c]) + (dv < 0 ? " (" + dv + ")" : "") : "--", col[3], yb, fs,
                    dv < -3 ? Dashboard.ORANGE : Dashboard.WHITE, Painter.CENTER, false);
            for (int k = 0; k < 4; k++) {
                int v = s.evByCorner[k][c];
                text(v > 0 ? String.valueOf(v) : "·", col[4 + k], yb, fs, v > 0 ? Dashboard.ORANGE : Dashboard.DIM, Painter.CENTER, v > 0);
            }
        }
    }

    // ---------------------------------------------------------------- VUELTAS
    private void drawLaps(Engineer e) {
        Session s = e.session;
        if (s.laps.isEmpty()) { text("Todavía no hay vueltas completas.", 512, 320, 22, Dashboard.DIM, Painter.CENTER, false); return; }
        Session.Lap best = s.best();
        int lo = Integer.MAX_VALUE, hi = 0;
        for (Session.Lap l : s.laps) if (l.ms > 0) { lo = Math.min(lo, l.ms); hi = Math.max(hi, l.ms); }
        // gráfico de barras: más alta = más lenta
        float gl = 60, gr = 990, gt = 86, gb = 280;
        text("TIEMPO POR VUELTA", 30, 100, 13, Dashboard.LABEL, Painter.LEFT, true);
        int n = s.laps.size();
        int first = Math.max(0, n - 30);
        float bw = (gr - gl) / Math.max(1, n - first);
        for (int i = first; i < n; i++) {
            Session.Lap l = s.laps.get(i);
            float x = gl + (i - first) * bw;
            if (l.ms <= 0) continue;
            float f = hi > lo ? (l.ms - lo) / (float) (hi - lo) : 0;
            float top = gb - 40 - f * (gb - gt - 60);
            round(x + bw * 0.15f, top, x + bw * 0.85f, gb, 4, l == best ? Dashboard.PURPLE : Dashboard.BLUE);
            text(String.valueOf(l.lap), x + bw / 2, gb + 16, 12, Dashboard.DIM, Painter.CENTER, false);
        }
        // tabla
        String[] head = {"VUELTA", "TIEMPO", "DIF.", "S1", "S2", "S3", "V. MÁX", "COMB.", "BLOQ", "PATIN", "SOBRE", "SUBV"};
        float[] col = {54, 150, 250, 335, 420, 505, 590, 668, 742, 810, 878, 946};
        int[] bs = {s.bestSector(0), s.bestSector(1), s.bestSector(2)};
        float y0 = 322;
        for (int i = 0; i < head.length; i++) text(head[i], col[i], y0, 13, Dashboard.LABEL, Painter.CENTER, true);
        int rows = (int) ((580 - y0 - 10) / 26);
        int start = Math.max(0, n - rows);
        for (int i = start; i < n; i++) {
            Session.Lap l = s.laps.get(i);
            float y = y0 + 26 * (i - start + 1);
            int c = l == best ? 0xffc9a6ff : Dashboard.WHITE;
            text(l.lap + (l.pit ? " P" : ""), col[0], y, 16, l.pit ? Dashboard.YELLOW : c, Painter.CENTER, true);
            text(Engineer.msText(l.ms), col[1], y, 16, c, Painter.CENTER, false);
            text(best != null && l.ms > 0 && l != best ? String.format(Locale.US, "+%.2f", (l.ms - best.ms) / 1000f) : l == best ? "mejor" : "--",
                    col[2], y, 16, c, Painter.CENTER, false);
            int[] sv = {l.s1, l.s2, l.s3};
            for (int k = 0; k < 3; k++)
                text(sv[k] > 0 ? String.format(Locale.US, "%.2f", sv[k] / 1000f) : "--", col[3 + k], y, 16,
                        sv[k] > 0 && sv[k] == bs[k] ? 0xffc9a6ff : sv[k] > 0 ? Dashboard.WHITE : Dashboard.DIM, Painter.CENTER, sv[k] > 0 && sv[k] == bs[k]);
            text(l.maxKmh > 0 ? String.valueOf(Math.round(l.maxKmh)) : "--", col[6], y, 16, Dashboard.WHITE, Painter.CENTER, false);
            text(l.fuelUsed > 0 ? String.format(Locale.US, "%.1f%%", l.fuelUsed) : "--", col[7], y, 16, Dashboard.WHITE, Painter.CENTER, false);
            int[] v = {l.lock, l.spin, l.over, l.under};
            for (int k = 0; k < 4; k++) text(v[k] > 0 ? String.valueOf(v[k]) : "·", col[8 + k], y, 16, v[k] > 0 ? Dashboard.ORANGE : Dashboard.DIM, Painter.CENTER, v[k] > 0);
        }
    }

    // ---------------------------------------------------------------- AUTO
    private void drawCar(Telemetry t, Engineer e) {
        Dynamics d = e.dyn;
        // círculo de fuerzas G
        float cx = 200, cy = 340, R = 210;
        text("FUERZAS G", 30, 100, 14, Dashboard.LABEL, Painter.LEFT, true);
        p.circle(X(cx), Y(cy), R * u, 0xff101114);
        for (int g = 1; g <= 3; g++) p.ring(X(cx), Y(cy), R * u * g / 3f, 1.5f * u, GRID);
        line(cx - R, cy, cx + R, cy, 1, GRID); line(cx, cy - R, cx, cy + R, 1, GRID);
        text("1G", cx + R / 3 + 4, cy - 4, 11, Dashboard.DIM, Painter.LEFT, false);
        text("2G", cx + 2 * R / 3 + 4, cy - 4, 11, Dashboard.DIM, Painter.LEFT, false);
        float k = R * u / 3f;  // px por G
        for (int i = 0; i < d.trailN; i++) {
            int idx = (d.trailPos - 1 - i + d.trailLat.length) % d.trailLat.length;
            p.circle(X(cx) + clamp(d.trailLat[idx]) * k, Y(cy) - clamp(d.trailLon[idx]) * k, 3 * u, 0x80ffe34d);
        }
        p.circle(X(cx) + clamp(d.gLat) * k, Y(cy) - clamp(d.gLon) * k, 10 * u, Dashboard.RED);
        text("acelera", cx, cy - R - 8, 12, Dashboard.DIM, Painter.CENTER, false);
        text("frena", cx, cy + R + 20, 12, Dashboard.DIM, Painter.CENTER, false);
        text(String.format(Locale.US, "lat %.2f  lon %.2f", Math.abs(d.gLat), d.gLon), cx, 584, 15, Dashboard.WHITE, Painter.CENTER, false);

        // ruedas: deslizamiento
        text("RUEDAS (deslizamiento)", 440, 100, 14, Dashboard.LABEL, Painter.LEFT, true);
        float[][] pos = {{450, 120}, {590, 120}, {450, 300}, {590, 300}};
        String[] nm = {"DI", "DD", "TI", "TD"};
        for (int i = 0; i < 4; i++) {
            float l = pos[i][0], tp = pos[i][1];
            float sl = d.slip[i] * 100;
            int c = sl < -25 ? Dashboard.ORANGE : sl > 15 ? Dashboard.PURPLE : Dashboard.GREEN;
            round(l, tp, l + 120, tp + 160, 10, 0xff101114);
            box(l, tp, l + 120, tp + 160, c);
            text(nm[i], l + 10, tp + 22, 14, Dashboard.LABEL, Painter.LEFT, true);
            text(String.format(Locale.US, "%+.0f%%", sl), l + 60, tp + 78, 30, c, Painter.CENTER, true);
            // barra: izquierda = bloqueo, derecha = patinaje
            round(l + 10, tp + 104, l + 110, tp + 116, 3, GRID);
            float f = Math.max(-1, Math.min(1, sl / 40f));
            if (f < 0) round(l + 60 + 50 * f, tp + 104, l + 60, tp + 116, 3, Dashboard.ORANGE);
            else round(l + 60, tp + 104, l + 60 + 50 * f, tp + 116, 3, Dashboard.PURPLE);
            text(Math.round(t.tyreTemp[i]) + "°C", l + 60, tp + 146, 16, Dashboard.tyreColor(t.tyreTemp[i]), Painter.CENTER, false);
        }
        text("− bloquea  ·  + patina", 570, 500, 13, Dashboard.DIM, Painter.CENTER, false);
        String bal = !d.steerAvailable ? "Subviraje: requiere GT7 actualizado (paquete B)"
                : d.understeerRatio > 1.4f ? "Subviraje ahora" : d.yawExcess > 0.15f ? "Sobreviraje ahora" : "Balance neutro";
        text(bal, 570, 530, 16, d.understeerRatio > 1.4f ? Dashboard.BLUE : d.yawExcess > 0.15f ? Dashboard.RED : Dashboard.GREEN, Painter.CENTER, true);

        // suspensión
        text("SUSPENSIÓN (mm)", 760, 100, 14, Dashboard.LABEL, Painter.LEFT, true);
        float[] sx0 = {770, 830, 890, 950};
        for (int i = 0; i < 4; i++) {
            float mm = t.suspHeight[i] * 1000;
            float f = Math.max(0, Math.min(1, mm / 150f));
            round(sx0[i], 130, sx0[i] + 40, 430, 6, GRID);
            round(sx0[i], 430 - 300 * f, sx0[i] + 40, 430, 6, mm < 15 ? Dashboard.RED : Dashboard.TEAL);
            text(nm[i], sx0[i] + 20, 452, 14, Dashboard.LABEL, Painter.CENTER, true);
            text(String.valueOf(Math.round(mm)), sx0[i] + 20, 476, 16, Dashboard.WHITE, Painter.CENTER, false);
        }
        text(String.format(Locale.US, "Altura carrocería %.0f mm", t.bodyHeight * 1000), 880, 512, 14, Dashboard.WHITE, Painter.CENTER, false);
        text(String.format(Locale.US, "G máx: curva %.1f · frenada %.1f · acel %.1f", d.maxGLat, d.maxGBrake, d.maxGAcc), 880, 540, 13, Dashboard.DIM, Painter.CENTER, false);
    }

    private static float clamp(float g) { return Math.max(-3f, Math.min(3f, g)); }
}
