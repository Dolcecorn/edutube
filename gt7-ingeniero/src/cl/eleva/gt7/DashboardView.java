package cl.eleva.gt7;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.view.MotionEvent;
import android.view.View;

/** Vista que redibuja el dashboard ~25 veces por segundo. */
final class DashboardView extends View implements Painter {

    private final MainActivity act;
    private final Dashboard dash = new Dashboard();
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
        synchronized (act.lock) {
            snap.copyFrom(act.telemetry);
            live = System.currentTimeMillis() - act.lastPacketAt < 2000;
            dash.draw(this, getWidth(), getHeight(), snap, act.engineer, act.connText, live, System.currentTimeMillis());
        }
        postInvalidateDelayed(40);
    }

    @Override public boolean onTouchEvent(MotionEvent e) {
        if (e.getAction() != MotionEvent.ACTION_UP) return true;
        float x = e.getX(), y = e.getY();
        if (x >= dash.menuL && x <= dash.menuR && y >= dash.menuT && y <= dash.menuB) act.showSettings();
        else if (x >= dash.engL && x <= dash.engR && y >= dash.engT && y <= dash.engB) act.speakStatus();
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
    public float width(String s, float size, boolean bold) { font(size, bold); return txt.measureText(s); }
}
