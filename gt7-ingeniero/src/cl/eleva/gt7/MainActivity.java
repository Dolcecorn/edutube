package cl.eleva.gt7;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.content.SharedPreferences;
import android.net.DhcpInfo;
import android.net.wifi.WifiManager;
import android.os.Bundle;
import android.os.Handler;
import android.speech.tts.TextToSpeech;
import android.text.InputType;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.SocketTimeoutException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Locale;

public class MainActivity extends Activity implements TextToSpeech.OnInitListener {
    static final int PORT_SEND = 33739, PORT_RECV = 33740;

    final Object lock = new Object();
    final Telemetry telemetry = new Telemetry();
    Engineer engineer;
    volatile long lastPacketAt;
    volatile String connText = "Buscando la PS5 en la red…";

    private SharedPreferences prefs;
    private TextToSpeech tts;
    private boolean ttsReady;
    private final Handler ui = new Handler();
    private volatile boolean running;
    private Thread worker;
    private DatagramSocket socket;
    private DashboardView view;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN | WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        prefs = getSharedPreferences("gt7", MODE_PRIVATE);
        engineer = new Engineer(new Engineer.Voice() {
            public void say(final String text, final boolean urgent) {
                ui.post(new Runnable() { public void run() { speak(text, urgent); } });
            }
        });
        applyPrefs();
        view = new DashboardView(this);
        setContentView(view);
        String eng = prefs.getString("motor", "");
        tts = eng.length() > 0 ? new TextToSpeech(this, this, eng) : new TextToSpeech(this, this);
    }

    @Override public void onInit(int status) {
        if (status != TextToSpeech.SUCCESS) return;
        Locale[] tries = {new Locale("es", "CL"), new Locale("es", "US"), new Locale("es", "ES"), new Locale("es")};
        for (Locale l : tries) {
            if (tts.isLanguageAvailable(l) >= TextToSpeech.LANG_AVAILABLE) { tts.setLanguage(l); break; }
        }
        tts.setSpeechRate(1.1f);
        tts.setPitch(prefs.getBoolean("grave", true) ? 0.8f : 1.0f);
        ttsReady = true;
    }

    void speak(String text, boolean urgent) {
        if (!ttsReady || !prefs.getBoolean("voz", true)) return;
        HashMap<String, String> p = new HashMap<String, String>();
        p.put(TextToSpeech.Engine.KEY_PARAM_STREAM, String.valueOf(android.media.AudioManager.STREAM_MUSIC));
        tts.speak(text, urgent ? TextToSpeech.QUEUE_FLUSH : TextToSpeech.QUEUE_ADD, p);
    }

    boolean isMuted() { return !prefs.getBoolean("voz", true); }

    // ---- preguntas por voz ----
    volatile boolean listening;
    private SpeechRecognizer recognizer;

    private void show(String s) {
        synchronized (lock) { engineer.lastMessage = s; engineer.lastMessageAt = System.currentTimeMillis(); }
    }

    void listen() {
        if (listening) { if (recognizer != null) recognizer.stopListening(); return; }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            String s;
            synchronized (lock) { s = engineer.status(telemetry); }
            show("(Esta tablet no tiene reconocimiento de voz) " + s);
            speak(s, true);
            return;
        }
        if (tts != null) tts.stop();
        if (recognizer == null) {
            recognizer = SpeechRecognizer.createSpeechRecognizer(this);
            recognizer.setRecognitionListener(new RecognitionListener() {
                public void onReadyForSpeech(Bundle b) { show("Te escucho… pregunta ahora."); }
                public void onBeginningOfSpeech() { }
                public void onRmsChanged(float v) { }
                public void onBufferReceived(byte[] b) { }
                public void onEndOfSpeech() { show("Pensando…"); }
                public void onPartialResults(Bundle b) { }
                public void onEvent(int t, Bundle b) { }
                public void onError(int err) {
                    listening = false;
                    String why = err == SpeechRecognizer.ERROR_NETWORK || err == SpeechRecognizer.ERROR_NETWORK_TIMEOUT
                            ? "sin conexión al servicio de voz" : err == SpeechRecognizer.ERROR_NO_MATCH || err == SpeechRecognizer.ERROR_SPEECH_TIMEOUT
                            ? "no te escuché" : "error " + err;
                    show("No pude entender (" + why + "). Toca RAD e intenta de nuevo.");
                }
                public void onResults(Bundle b) {
                    listening = false;
                    ArrayList<String> r = b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                    if (r == null || r.isEmpty()) { show("No te escuché. Toca RAD e intenta de nuevo."); return; }
                    String a;
                    synchronized (lock) { a = engineer.answer(r.get(0), telemetry); }
                    show("«" + r.get(0) + "» " + a);
                    speak(a, true);
                }
            });
        }
        Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        i.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "es-CL");
        i.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3);
        i.putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, getPackageName());
        listening = true;
        show("Abriendo micrófono…");
        recognizer.startListening(i);
    }

    /** Botones redondos del dashboard. */
    void onButton(int id) {
        String s = null;
        synchronized (lock) {
            switch (id) {
                case Dashboard.B_RAD: break;
                case Dashboard.B_FUEL: s = engineer.fuelReport(telemetry); break;
                case Dashboard.B_TYR: s = engineer.tyreReport(telemetry); break;
                case Dashboard.B_LAP: s = engineer.lapReport(telemetry); break;
                case Dashboard.B_PIT: s = engineer.pitReport(telemetry); break;
                case Dashboard.B_OK: s = engineer.lastMessage.length() > 0 ? engineer.lastMessage : null; break;
                default: break;
            }
            if (s != null) { engineer.lastMessage = s; engineer.lastMessageAt = System.currentTimeMillis(); }
        }
        if (s != null) { speak(s, true); return; }
        android.media.AudioManager am = (android.media.AudioManager) getSystemService(AUDIO_SERVICE);
        switch (id) {
            case Dashboard.B_VOLDN:
            case Dashboard.B_VOLUP:
                am.adjustStreamVolume(android.media.AudioManager.STREAM_MUSIC,
                        id == Dashboard.B_VOLUP ? android.media.AudioManager.ADJUST_RAISE : android.media.AudioManager.ADJUST_LOWER,
                        android.media.AudioManager.FLAG_SHOW_UI);
                speak("Radio", true);
                break;
            case Dashboard.B_MUTE:
                boolean nowMuted = !isMuted();
                prefs.edit().putBoolean("voz", !nowMuted).commit();
                if (nowMuted) { if (tts != null) tts.stop(); }
                else speak("Radio activada", true);
                break;
            case Dashboard.B_SET: showSettings(); break;
            case Dashboard.B_RAD: listen(); break;
            default: break;
        }
    }

    private void applyPrefs() {
        engineer.midLapCalls = prefs.getBoolean("mitad", true);
        engineer.tyreCalls = prefs.getBoolean("neumaticos", true);
    }

    @Override protected void onResume() {
        super.onResume();
        view.setSystemUiVisibility(View.SYSTEM_UI_FLAG_LOW_PROFILE);
        start();
    }

    @Override protected void onPause() {
        stop();
        super.onPause();
    }

    @Override protected void onDestroy() {
        if (tts != null) tts.shutdown();
        if (recognizer != null) recognizer.destroy();
        super.onDestroy();
    }

    // ---- recepción ----
    private void start() {
        stop();
        running = true;
        final boolean demo = prefs.getBoolean("demo", false);
        worker = new Thread(new Runnable() { public void run() { if (demo) runDemo(); else runUdp(); } }, "gt7");
        worker.start();
    }

    private void stop() {
        running = false;
        DatagramSocket s = socket;
        if (s != null) s.close();
        if (worker != null) { try { worker.join(1500); } catch (InterruptedException ignored) { } }
        worker = null;
    }

    private void feed(byte[] buf, int len, Telemetry t) {
        if (!t.decrypt(buf, len)) return;
        synchronized (lock) {
            telemetry.copyFrom(t);
            engineer.onPacket(t);
            lastPacketAt = System.currentTimeMillis();
        }
    }

    private void runDemo() {
        connText = "MODO DEMOSTRACIÓN (datos simulados)";
        synchronized (lock) { engineer.reset(); }
        Simulator sim = new Simulator();
        Telemetry t = new Telemetry();
        long next = System.nanoTime();
        while (running) {
            byte[] p = sim.next();
            feed(p, p.length, t);
            next += 16683000L;
            long wait = (next - System.nanoTime()) / 1000000L;
            if (wait > 0) { try { Thread.sleep(wait); } catch (InterruptedException e) { return; } }
        }
    }

    private ArrayList<InetAddress> targets(InetAddress locked) {
        ArrayList<InetAddress> out = new ArrayList<InetAddress>();
        String ip = prefs.getString("ip", "").trim();
        try {
            if (ip.length() > 0) { out.add(InetAddress.getByName(ip)); return out; }
            if (locked != null) { out.add(locked); return out; }
            out.add(InetAddress.getByName("255.255.255.255"));
            WifiManager wm = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            DhcpInfo d = wm != null ? wm.getDhcpInfo() : null;
            if (d != null && d.ipAddress != 0) {
                int bc = (d.ipAddress & d.netmask) | ~d.netmask;
                byte[] q = new byte[4];
                for (int k = 0; k < 4; k++) q[k] = (byte) (bc >> (k * 8));
                out.add(InetAddress.getByAddress(q));
            }
        } catch (Exception ignored) { }
        return out;
    }

    private void runUdp() {
        String ip = prefs.getString("ip", "").trim();
        connText = ip.length() > 0 ? "Conectando con la PS5 " + ip + "…" : "Buscando la PS5 en la red…";
        Telemetry t = new Telemetry();
        byte[] buf = new byte[2048];
        byte[] hb = {'A'};
        InetAddress locked = null;
        while (running) {
            try {
                DatagramSocket s = new DatagramSocket(null);
                s.setReuseAddress(true);
                s.setBroadcast(true);
                s.bind(new InetSocketAddress(PORT_RECV));
                s.setSoTimeout(500);
                socket = s;
                long lastHb = 0;
                while (running) {
                    long now = System.currentTimeMillis();
                    if (now - lastHb > 1000) {   // GT7 deja de mandar si no recibe "A" cada ~100 paquetes
                        lastHb = now;
                        for (InetAddress a : targets(locked)) {
                            try { s.send(new DatagramPacket(hb, 1, a, PORT_SEND)); } catch (Exception ignored) { }
                        }
                        if (now - lastPacketAt > 5000 && locked != null && ip.length() == 0) {
                            locked = null;  // se perdió: volver a buscar
                            connText = "Buscando la PS5 en la red…";
                        }
                    }
                    DatagramPacket pk = new DatagramPacket(buf, buf.length);
                    try { s.receive(pk); } catch (SocketTimeoutException e) { continue; }
                    if (pk.getLength() < Telemetry.PACKET_SIZE) continue;
                    feed(buf, pk.getLength(), t);
                    if (locked == null || !locked.equals(pk.getAddress())) {
                        locked = pk.getAddress();
                        connText = "Conectado a la PS5 " + locked.getHostAddress();
                    }
                }
                s.close();
            } catch (Exception e) {
                if (!running) break;
                connText = "Error de red: " + e.getMessage();
                try { Thread.sleep(2000); } catch (InterruptedException ie) { return; }
            } finally {
                if (socket != null) socket.close();
                socket = null;
            }
        }
    }

    // ---- ajustes ----
    void showSettings() {
        final float d = getResources().getDisplayMetrics().density;
        int pad = (int) (16 * d);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(pad, pad, pad, pad);

        TextView l = new TextView(this);
        l.setText("IP de la PS5 (déjala vacía para buscarla sola):");
        box.addView(l);
        final EditText ip = new EditText(this);
        ip.setSingleLine(true);
        ip.setInputType(InputType.TYPE_CLASS_PHONE);
        ip.setHint("Automático, ej. 192.168.1.20");
        ip.setText(prefs.getString("ip", ""));
        box.addView(ip);

        final CheckBox voz = check(box, "Voz del ingeniero", "voz", true);
        final CheckBox mitad = check(box, "Avisar el delta a mitad de vuelta", "mitad", true);
        final CheckBox neu = check(box, "Avisos de neumáticos y motor", "neumaticos", true);
        final CheckBox grave = check(box, "Voz más grave", "grave", true);
        final CheckBox demo = check(box, "Modo demostración (sin PS5)", "demo", false);

        TextView le = new TextView(this);
        le.setText("Motor de voz:");
        le.setPadding(0, pad / 2, 0, 0);
        box.addView(le);
        final RadioGroup motores = new RadioGroup(this);
        final ArrayList<String> pkgs = new ArrayList<String>();
        String actual = prefs.getString("motor", "");
        try {
            for (TextToSpeech.EngineInfo ei : tts.getEngines()) {
                RadioButton rb = new RadioButton(this);
                rb.setText(ei.label);
                rb.setId(1000 + pkgs.size());
                pkgs.add(ei.name);
                motores.addView(rb);
                if (ei.name.equals(actual) || (actual.length() == 0 && ei.name.equals(tts.getDefaultEngine()))) motores.check(rb.getId());
            }
        } catch (Exception ignored) { }
        box.addView(motores);

        new AlertDialog.Builder(this)
            .setTitle("Ingeniero GT7")
            .setView(scroll(box))
            .setPositiveButton("Guardar", new DialogInterface.OnClickListener() {
                public void onClick(DialogInterface di, int w) {
                    prefs.edit().putString("ip", ip.getText().toString().trim())
                        .putBoolean("voz", voz.isChecked()).putBoolean("mitad", mitad.isChecked())
                        .putBoolean("neumaticos", neu.isChecked()).putBoolean("demo", demo.isChecked())
                        .putBoolean("grave", grave.isChecked()).commit();
                    int sel = motores.getCheckedRadioButtonId() - 1000;
                    String nuevo = sel >= 0 && sel < pkgs.size() ? pkgs.get(sel) : "";
                    if (!nuevo.equals(prefs.getString("motor", "")) && nuevo.length() > 0) {
                        prefs.edit().putString("motor", nuevo).commit();
                        ttsReady = false;
                        tts.shutdown();
                        tts = new TextToSpeech(MainActivity.this, MainActivity.this, nuevo);
                    } else if (ttsReady) tts.setPitch(grave.isChecked() ? 0.8f : 1.0f);
                    synchronized (lock) { applyPrefs(); engineer.reset(); lastPacketAt = 0; }
                    start();
                }
            })
            .setNeutralButton("Probar voz", new DialogInterface.OnClickListener() {
                public void onClick(DialogInterface di, int w) {
                    if (!ttsReady) Toast.makeText(MainActivity.this, "La voz aún no está lista", Toast.LENGTH_SHORT).show();
                    boolean was = prefs.getBoolean("voz", true);
                    prefs.edit().putBoolean("voz", true).commit();
                    speak("Radio OK. Te escucho fuerte y claro, vamos por esa carrera.", true);
                    prefs.edit().putBoolean("voz", was).commit();
                }
            })
            .setNegativeButton("Cerrar", null)
            .show();
    }

    private View scroll(View v) {
        android.widget.ScrollView sv = new android.widget.ScrollView(this);
        sv.addView(v);
        return sv;
    }

    private CheckBox check(LinearLayout box, String label, String key, boolean def) {
        CheckBox c = new CheckBox(this);
        c.setText(label);
        c.setChecked(prefs.getBoolean(key, def));
        box.addView(c);
        return c;
    }
}
