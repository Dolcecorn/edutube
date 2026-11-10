package cl.eleva.gt7;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Rect;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.view.MotionEvent;
import android.view.View;

/** Vista que redibuja el dashboard ~25 veces por segundo. */
final class DashboardView extends View implements Painter {

    private final MainActivity act;
    private final Dashboard dash = new Dashboard();
    private final Analysis analysis = new Analysis();
    private boolean showAnalysis;
    private int seenRaceEnds;
    private float downX, downY;
    private final Telemetry snap = new Telemetry();
    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint txt = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF rf = new RectF();
    private Canvas c;

    DashboardView(MainActivity a) {
        super(a);
        act = a;
        stroke.setStyle(Paint.Style.STROKE);
        setKeepScreenOn(true);
    }

    @Override protected void onDraw(Canvas canvas) {
        c = canvas;
        boolean live;
        dash.muted = act.isMuted();
        dash.listening = act.listening;
        synchronized (act.lock) {
            snap.copyFrom(act.telemetry);
            act.engineer.tick();   // el resumen final sale aunque ya no lleguen paquetes
            live = System.currentTimeMillis() - act.lastPacketAt < 2000;
            if (act.engineer.raceEnds != seenRaceEnds) {   // terminó la carrera: abre el análisis
                seenRaceEnds = act.engineer.raceEnds;
                showAnalysis = true;
                analysis.tab = 0;
                new Thread(new Runnable() { public void run() { analysis.csvPath = act.exportCsv(); } }).start();
            }
            if (showAnalysis) analysis.draw(this, getWidth(), getHeight(), snap, act.engineer, System.currentTimeMillis());
            else dash.draw(this, getWidth(), getHeight(), snap, act.engineer, act.connText, live, System.currentTimeMillis());
        }
        postInvalidateDelayed(40);
    }

    @Override public boolean onTouchEvent(MotionEvent e) {
        if (e.getAction() == MotionEvent.ACTION_DOWN) { downX = e.getX(); downY = e.getY(); return true; }
        if (e.getAction() != MotionEvent.ACTION_UP) return true;
        float x = e.getX(), y = e.getY();
        float dx = x - downX, dy = y - downY;
        if (Math.abs(dx) > getWidth() * 0.12f && Math.abs(dx) > Math.abs(dy) * 1.5f) {   // deslizar
            if (dx < 0 && !showAnalysis) showAnalysis = true;
            else if (dx > 0 && showAnalysis) showAnalysis = false;
            return true;
        }
        if (showAnalysis) {
            if (y >= analysis.tabT && y <= analysis.tabB) {
                if (x >= analysis.backL && x <= analysis.backR) { showAnalysis = false; return true; }
                for (int i = 0; i < Analysis.TABS.length; i++)
                    if (x >= analysis.tabL[i] && x <= analysis.tabR[i]) { analysis.tab = i; return true; }
            }
            return true;
        }
        float r = dash.btnR * 1.25f;   // zona táctil un poco más grande que el botón
        for (int i = 0; i < 10; i++) {
            float bx = x - dash.btnX[i], by = y - dash.btnY[i];
            if (bx * bx + by * by <= r * r) {
                dash.pressed = i;
                dash.pressedAt = System.currentTimeMillis();
                act.onButton(i);
                return true;
            }
        }
        return true;
    }

    // ---- Painter con Canvas ----
    public void rect(float l, float t, float r, float b, int argb) { fill.setColor(argb); c.drawRect(l, t, r, b, fill); }
    public void round(float l, float t, float r, float b, float rad, int argb) {
        fill.setColor(argb); rf.set(l, t, r, b); c.drawRoundRect(rf, rad, rad, fill);
    }
    public void outline(float l, float t, float r, float b, float rad, float w, int argb) {
        stroke.setColor(argb); stroke.setStrokeWidth(w); rf.set(l, t, r, b); c.drawRoundRect(rf, rad, rad, stroke);
    }
    private void font(float size, boolean bold) {
        txt.setTextSize(size);
        txt.setTypeface(bold ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
    }
    public void text(String s, float x, float y, float size, int argb, int align, boolean bold) {
        font(size, bold);
        txt.setColor(argb);
        txt.setTextAlign(align == CENTER ? Paint.Align.CENTER : align == RIGHT ? Paint.Align.RIGHT : Paint.Align.LEFT);
        c.drawText(s, x, y, txt);
    }
    public void circle(float cx, float cy, float r, int argb) { fill.setColor(argb); c.drawCircle(cx, cy, r, fill); }
    public void ring(float cx, float cy, float r, float w, int argb) {
        stroke.setColor(argb); stroke.setStrokeWidth(w); c.drawCircle(cx, cy, r, stroke);
    }
    private Bitmap emblem;
    private final Rect src = new Rect();
    private final Paint bmp = new Paint(Paint.FILTER_BITMAP_FLAG | Paint.ANTI_ALIAS_FLAG);
    public void emblem(float l, float t, float r, float b) {
        if (emblem == null) emblem = BitmapFactory.decodeResource(getResources(), R.drawable.emblema);
        if (emblem == null) return;
        float s = Math.min((r - l) / emblem.getWidth(), (b - t) / emblem.getHeight());
        float w = emblem.getWidth() * s, h = emblem.getHeight() * s;
        src.set(0, 0, emblem.getWidth(), emblem.getHeight());
        rf.set((l + r - w) / 2, (t + b - h) / 2, (l + r + w) / 2, (t + b + h) / 2);
        c.drawBitmap(emblem, src, rf, bmp);
    }
    private final Paint linePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    public void line(float x1, float y1, float x2, float y2, float w, int argb) {
        linePaint.setColor(argb); linePaint.setStrokeWidth(w); linePaint.setStrokeCap(Paint.Cap.ROUND);
        c.drawLine(x1, y1, x2, y2, linePaint);
    }
    private Paint carbonPaint;
    public void carbon(float l, float t, float r, float b) {
        if (carbonPaint == null) {
            int n = 16;
            Bitmap tile = Bitmap.createBitmap(Dashboard.carbonTile(n), n, n, Bitmap.Config.ARGB_8888);
            carbonPaint = new Paint();
            carbonPaint.setShader(new android.graphics.BitmapShader(tile, android.graphics.Shader.TileMode.REPEAT, android.graphics.Shader.TileMode.REPEAT));
        }
        c.drawRect(l, t, r, b, carbonPaint);
    }
    public float width(String s, float size, boolean bold) { font(size, bold); return txt.measureText(s); }
}
