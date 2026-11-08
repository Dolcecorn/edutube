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
    public float width(String s, float size, boolean bold) { return (float) g.getFontMetrics(f(size, bold)).getStringBounds(s, g).getWidth(); }

    static void shot(String file, int seconds, boolean live) throws Exception {
        Simulator sim = new Simulator();
        Telemetry t = new Telemetry();
        Engineer e = new Engineer(null);
        for (int i = 0; i < seconds * 60; i++) { byte[] p = sim.next(); t.decrypt(p, p.length); e.onPacket(t); }
        if (!live) { t = new Telemetry(); e = new Engineer(null); }
        BufferedImage img = new BufferedImage(1024, 600, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = img.createGraphics();
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
        new Dashboard().draw(new Preview(g), 1024, 600, t, e, live ? "Conectado a 192.168.1.20" : "Buscando la PS5 en la red…", live, 0);
        ImageIO.write(img, "png", new File(file));
    }

    public static void main(String[] a) throws Exception {
        shot(a[0] + "/dash-carrera.png", 300, true);
        shot(a[0] + "/dash-esperando.png", 0, false);
    }
}
