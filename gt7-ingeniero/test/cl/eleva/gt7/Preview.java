package cl.eleva.gt7;

import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;

/** Dibuja el dashboard con Java2D para ver cómo queda sin la tablet. */
public class Preview implements Painter {
    final Graphics2D g;
    Preview(Graphics2D g) { this.g = g; }
    private void c(int argb) { g.setColor(new Color(argb, true)); }
    public void rect(float l, float t, float r, float b, int a) { c(a); g.fill(new java.awt.geom.Rectangle2D.Float(l, t, r - l, b - t)); }
    public void round(float l, float t, float r, float b, float rad, int a) { c(a); g.fill(new java.awt.geom.RoundRectangle2D.Float(l, t, r - l, b - t, rad * 2, rad * 2)); }
    public void outline(float l, float t, float r, float b, float rad, float w, int a) { c(a); g.setStroke(new BasicStroke(w)); g.draw(new java.awt.geom.RoundRectangle2D.Float(l, t, r - l, b - t, rad * 2, rad * 2)); }
    private Font f(float size, boolean bold) { return new Font("Roboto", bold ? Font.BOLD : Font.PLAIN, 1).deriveFont(size); }
    public void text(String s, float x, float y, float size, int a, int align, boolean bold) {
        c(a); g.setFont(f(size, bold));
        float w = width(s, size, bold);
        g.drawString(s, align == CENTER ? x - w / 2 : align == RIGHT ? x - w : x, y);
    }
    public void circle(float cx, float cy, float r, int a) { c(a); g.fill(new java.awt.geom.Ellipse2D.Float(cx - r, cy - r, 2 * r, 2 * r)); }
    public void ring(float cx, float cy, float r, float w, int a) { c(a); g.setStroke(new BasicStroke(w)); g.draw(new java.awt.geom.Ellipse2D.Float(cx - r, cy - r, 2 * r, 2 * r)); }
    static java.awt.Image em;
    public void emblem(float l, float t, float r, float b) {
        try { if (em == null) em = ImageIO.read(new File("res/drawable/emblema.png")); } catch (Exception e) { return; }
        float s = Math.min((r - l) / em.getWidth(null), (b - t) / em.getHeight(null));
        int w = Math.round(em.getWidth(null) * s), h = Math.round(em.getHeight(null) * s);
        g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BICUBIC);
        g.drawImage(em, Math.round((l + r - w) / 2), Math.round((t + b - h) / 2), w, h, null);
    }
    public void line(float x1, float y1, float x2, float y2, float w, int a) {
        c(a); g.setStroke(new BasicStroke(w, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
        g.draw(new java.awt.geom.Line2D.Float(x1, y1, x2, y2));
    }
    static TexturePaint carbonPaint;
    public void carbon(float l, float t, float r, float b) {
        if (carbonPaint == null) {
            int n = 16;
            BufferedImage im = new BufferedImage(n, n, BufferedImage.TYPE_INT_ARGB);
            im.setRGB(0, 0, n, n, Dashboard.carbonTile(n), 0, n);
            carbonPaint = new TexturePaint(im, new java.awt.geom.Rectangle2D.Float(0, 0, n, n));
        }
        Paint old = g.getPaint(); g.setPaint(carbonPaint);
        g.fill(new java.awt.geom.Rectangle2D.Float(l, t, r - l, b - t)); g.setPaint(old);
    }
    public float width(String s, float size, boolean bold) { return (float) g.getFontMetrics(f(size, bold)).getStringBounds(s, g).getWidth(); }

    static int W = 1024, H = 600;
    static void shot(String file, int seconds, boolean live) throws Exception {
        Simulator sim = new Simulator();
        Telemetry t = new Telemetry();
        Engineer e = new Engineer(null);
        for (int i = 0; i < seconds * 60; i++) { byte[] p = sim.next(); t.decrypt(p, p.length); e.onPacket(t); }
        if (!live) { t = new Telemetry(); e = new Engineer(null); }
        else e.lastMessageAt = System.currentTimeMillis();
        BufferedImage img = new BufferedImage(W, H, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = img.createGraphics();
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
        new Dashboard().draw(new Preview(g), W, H, t, e, live ? "Conectado a la PS5 192.168.1.20" : "Buscando la PS5 en la red…", live, System.currentTimeMillis() / 500 * 500);
        ImageIO.write(img, "png", new File(file));
    }

    static void analysis(String dir, int seconds) throws Exception {
        Simulator sim = new Simulator();
        Telemetry t = new Telemetry();
        Engineer e = new Engineer(null);
        for (int i = 0; i < seconds * 60; i++) { byte[] p = sim.next(); t.decrypt(p, p.length); e.onPacket(t); }
        Analysis an = new Analysis();
        an.csvPath = "/sdcard/IngenieroGT7/carrera.csv";
        for (int tab = 0; tab < Analysis.TABS.length; tab++) {
            an.tab = tab;
            BufferedImage img = new BufferedImage(1024, 552, BufferedImage.TYPE_INT_RGB);
            Graphics2D g = img.createGraphics();
            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
            an.draw(new Preview(g), 1024, 552, t, e, 0);
            ImageIO.write(img, "png", new File(dir + "/analisis-" + tab + ".png"));
        }
        java.nio.file.Files.write(new File(dir + "/carrera.csv").toPath(), e.session.csv().getBytes("UTF-8"));
    }

    public static void main(String[] a) throws Exception {
        analysis(a[0], a.length > 1 ? Integer.parseInt(a[1]) : 720);
        shot(a[0] + "/dash-carrera.png", 300, true);
        W = 1024; H = 552;   // tablet con barra de navegación
        shot(a[0] + "/dash-1024x552.png", 300, true);
        W = 1024; H = 600;
        shot(a[0] + "/dash-esperando.png", 0, false);
    }
}
