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
        engineer.setup = new Engineer.SetupProvider() {
            public String reminder(int car) { return setupReminder(car); }
        };
        engineer.tracks.load(readFile("pistas.txt"));
        engineer.tracks.loadBuiltin(readRaw(R.raw.pistas_gt7));
        registerReceiver(new android.content.BroadcastReceiver() {
            @Override public void onReceive(Context c, Intent i) {
                int lv = i.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL, -1), sc = i.getIntExtra(android.os.BatteryManager.EXTRA_SCALE, 100);
                int st = i.getIntExtra(android.os.BatteryManager.EXTRA_STATUS, -1);
                batteryPct = lv >= 0 && sc > 0 ? Math.round(100f * lv / sc) : -1;
                charging = st == android.os.BatteryManager.BATTERY_STATUS_CHARGING || st == android.os.BatteryManager.BATTERY_STATUS_FULL;
            }
        }, new android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        engineer.trackSaver = new Engineer.TrackSaver() {
            public void save(final String data) {
                new Thread(new Runnable() { public void run() { writeFile("pistas.txt", data); } }).start();
            }
        };
        view = new DashboardView(this);
        setContentView(view);
        if (!prefs.getBoolean("sin_ayuda", false)) showHelp(true);
        String eng = prefs.getString("motor", "");
        tts = eng.length() > 0 ? new TextToSpeech(this, this, eng) : new TextToSpeech(this, this);
    }

    @Override public void onInit(int status) {
        if (status != TextToSpeech.SUCCESS) { ui.postDelayed(new Runnable() { public void run() { restartTts(); } }, 3000); return; }
        ttsReady = true;
        applyVoice(prefs.getString("acento", "es-CL"), prefs.getFloat("rapidez", 1.1f), prefs.getBoolean("grave", true));
        flushPending();
    }

    // ---- voz robusta: con poca memoria Android puede cerrar el motor de voz; se reintenta ----
    private final ArrayList<String> pending = new ArrayList<String>();
    private final ArrayList<Long> pendingAt = new ArrayList<Long>();
    private long lastRestart;

    private void queuePending(String part) {
        if (pending.size() > 12) { pending.remove(0); pendingAt.remove(0); }
        pending.add(part); pendingAt.add(System.currentTimeMillis());
    }

    private void flushPending() {
        long now = System.currentTimeMillis();
        ArrayList<String> todo = new ArrayList<String>();
        for (int i = 0; i < pending.size(); i++) if (now - pendingAt.get(i) < 30000) todo.add(pending.get(i));   // lo viejo ya no sirve
        pending.clear(); pendingAt.clear();
        for (String part : todo) speakPart(part, false);
    }

    private void restartTts() {
        long now = System.currentTimeMillis();
        if (now - lastRestart < 4000) return;
        lastRestart = now;
        ttsReady = false;
        try { if (tts != null) tts.shutdown(); } catch (Exception ignored) { }
        String eng = prefs.getString("motor", "");
        tts = eng.length() > 0 ? new TextToSpeech(this, this, eng) : new TextToSpeech(this, this);
    }

    private int speakFailures;

    private void speakPart(String part, boolean flush) {
        if (!ttsReady) { queuePending(part); return; }
        HashMap<String, String> p = new HashMap<String, String>();
        p.put(TextToSpeech.Engine.KEY_PARAM_STREAM, String.valueOf(android.media.AudioManager.STREAM_MUSIC));
        int r;
        try { r = tts.speak(part, flush ? TextToSpeech.QUEUE_FLUSH : TextToSpeech.QUEUE_ADD, p); }
        catch (Exception e) { r = TextToSpeech.ERROR; }
        if (r == TextToSpeech.SUCCESS) { speakFailures = 0; return; }
        // el motor de voz se cayó: guarda el texto y lo vuelve a intentar
        queuePending(part);
        speakFailures++;
        if (speakFailures >= 2) restartTts();
        else ui.postDelayed(new Runnable() { public void run() { if (ttsReady && !pending.isEmpty()) flushPending(); } }, 1500);
    }

    static final String[] ACENTOS = {"es-CL", "es-US", "es-MX", "es-ES"};
    static final String[] ACENTO_NOMBRE = {"Chile", "Latino (EE.UU.)", "México", "España"};
    static final float[] RAPIDEZ = {0.9f, 1.1f, 1.3f};
    static final String[] RAPIDEZ_NOMBRE = {"Lenta", "Normal", "Rápida"};

    private static Locale loc(String tag) { String[] p = tag.split("-"); return new Locale(p[0], p.length > 1 ? p[1] : ""); }

    private boolean available(String tag) {
        try { return ttsReady && tts.isLanguageAvailable(loc(tag)) >= TextToSpeech.LANG_COUNTRY_AVAILABLE; } catch (Exception e) { return false; }
    }

    /** Usa el acento pedido; si la tablet no lo tiene, el primer español disponible. */
    private void applyVoice(String acento, float rate, boolean grave) {
        if (!ttsReady) return;
        ArrayList<String> tries = new ArrayList<String>();
        tries.add(acento);
        for (String a : ACENTOS) tries.add(a);
        tries.add("es");
        for (String tag : tries) {
            if (tts.isLanguageAvailable(loc(tag)) >= TextToSpeech.LANG_AVAILABLE) { tts.setLanguage(loc(tag)); break; }
        }
        tts.setSpeechRate(rate);
        tts.setPitch(grave ? 0.8f : 1.0f);
    }

    void speak(String text, boolean urgent) {
        if (!prefs.getBoolean("voz", true)) return;
        // los textos largos (como el resumen final) se dicen por partes
        boolean first = true;
        for (String part : chunks(text, 220)) {
            speakPart(part, urgent && first);
            first = false;
        }
    }

    static ArrayList<String> chunks(String text, int max) {
        ArrayList<String> out = new ArrayList<String>();
        StringBuilder cur = new StringBuilder();
        for (String s : text.split("(?<=[.!?;:])\\s+")) {
            if (cur.length() > 0 && cur.length() + s.length() + 1 > max) { out.add(cur.toString()); cur.setLength(0); }
            if (cur.length() > 0) cur.append(' ');
            cur.append(s);
            while (cur.length() > max * 2) {   // frase larguísima: corta en una coma o espacio
                int k = cur.lastIndexOf(", ", max); if (k < max / 2) k = cur.lastIndexOf(" ", max);
                if (k <= 0) break;
                out.add(cur.substring(0, k + 1).trim()); cur.delete(0, k + 1);
            }
        }
        if (cur.length() > 0) out.add(cur.toString());
        return out;
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
                    synchronized (lock) { a = engineer.answer(r.get(0), telemetry); saveEngineerPrefs(); }
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

    /** Guarda el historial de la carrera en /sdcard/IngenieroGT7/ (se saca con adb pull). */
    String exportCsv() {
        final String csv;
        synchronized (lock) { csv = engineer.session.csv(); }
        try {
            java.io.File dir = new java.io.File(android.os.Environment.getExternalStorageDirectory(), "IngenieroGT7");
            dir.mkdirs();
            String name = "carrera-" + new java.text.SimpleDateFormat("yyyyMMdd-HHmm", Locale.US).format(new java.util.Date()) + ".csv";
            java.io.File f = new java.io.File(dir, name);
            java.io.FileOutputStream out = new java.io.FileOutputStream(f);
            try { out.write(csv.getBytes("UTF-8")); } finally { out.close(); }
            return f.getAbsolutePath();
        } catch (Exception e) {
            return "";
        }
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
        engineer.lapCalls = prefs.getBoolean("tiempos", true);
        engineer.fuelCalls = prefs.getBoolean("combustible", true);
        engineer.midLapCalls = prefs.getBoolean("mitad", true);
        engineer.tyreCalls = prefs.getBoolean("neumaticos", true);
        engineer.coachCalls = prefs.getBoolean("consejos", true);
    }

    /** Guarda lo que el piloto prendió o apagó por voz. */
    private void saveEngineerPrefs() {
        prefs.edit().putBoolean("tiempos", engineer.lapCalls).putBoolean("combustible", engineer.fuelCalls)
            .putBoolean("mitad", engineer.midLapCalls).putBoolean("neumaticos", engineer.tyreCalls)
            .putBoolean("consejos", engineer.coachCalls).commit();
    }

    /** Recordatorio de parrilla con el TCS y el balance de frenos guardados para este auto. */
    String setupReminder(int car) {
        String tcs = prefs.getString("tcs_" + car, "").trim(), bb = prefs.getString("bb_" + car, "").trim();
        if (tcs.length() == 0 && bb.length() == 0) return null;
        StringBuilder sb = new StringBuilder("Antes de largar: ");
        if (tcs.length() > 0) sb.append("TCS en ").append(signed(tcs));
        if (tcs.length() > 0 && bb.length() > 0) sb.append(" y ");
        if (bb.length() > 0) sb.append("balance de frenos en ").append(signed(bb));
        return sb.append(".").toString();
    }

    private static String signed(String v) {
        if (v.startsWith("-")) return "menos " + v.substring(1);
        if (v.startsWith("+")) return "más " + v.substring(1);
        return v;
    }

    private void showHelp(boolean first) {
        AlertDialog.Builder b = new AlertDialog.Builder(this)
            .setTitle("Habla con tu ingeniero")
            .setMessage("Toca el botón RAD y di lo que quieres:\n\n"
                + "• \"Desactiva los consejos\" / \"Activa los consejos\"\n"
                + "• \"Apaga los tiempos\", \"el combustible\", \"los neumáticos\" o \"el delta\" (y \"activa…\" para volver)\n"
                + "• \"No me digas nada\": sólo el plan de combustible, lo crítico y la bandera\n"
                + "• \"Activa todo\": te habla de todo\n\n"
                + "Preguntas: \"¿Cuándo entro a boxes?\", \"¿Cuánta bencina queda?\", \"¿Cómo voy?\", "
                + "\"¿Cuántas vueltas faltan?\", \"¿Cómo están los neumáticos?\"\n\n"
                + "Di \"ayuda\" para escuchar esto. En SET guardas el TCS y el balance de frenos de cada auto.")
            .setPositiveButton("Entendido", null);
        if (first) b.setNegativeButton("No mostrar más", new DialogInterface.OnClickListener() {
            public void onClick(DialogInterface di, int w) { prefs.edit().putBoolean("sin_ayuda", true).commit(); }
        });
        b.show();
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
    private WifiManager.WifiLock wifiLock;

    private void start() {
        stop();
        running = true;
        // sin esto el wifi de la tablet entra en ahorro de energía y los paquetes llegan a tirones
        try {
            if (wifiLock == null) {
                WifiManager wm = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
                wifiLock = wm.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "gt7");
                wifiLock.setReferenceCounted(false);
            }
            wifiLock.acquire();
        } catch (Exception ignored) { }
        final boolean demo = prefs.getBoolean("demo", false);
        worker = new Thread(new Runnable() { public void run() { if (demo) runDemo(); else runUdp(); } }, "gt7");
        worker.start();
    }

    private void stop() {
        running = false;
        try { if (wifiLock != null && wifiLock.isHeld()) wifiLock.release(); } catch (Exception ignored) { }
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
        byte[] hb = {'B'};   // "B" trae el volante; si la PS5 no responde, se prueba con "A"
        long hbSince = System.currentTimeMillis();
        InetAddress locked = null;
        while (running) {
            try {
                DatagramSocket s = new DatagramSocket(null);
                s.setReuseAddress(true);
                s.setBroadcast(true);
                s.bind(new InetSocketAddress(PORT_RECV));
                s.setSoTimeout(500);
                try { s.setReceiveBufferSize(256 * 1024); } catch (Exception ignored) { }
                socket = s;
                long lastHb = 0;
                while (running) {
                    long now = System.currentTimeMillis();
                    if (now - lastHb > 1000) {   // GT7 deja de mandar si no recibe el latido cada ~100 paquetes
                        lastHb = now;
                        if (now - lastPacketAt > 6000 && now - hbSince > 6000) {
                            hb[0] = hb[0] == 'B' ? (byte) 'A' : (byte) 'B';
                            hbSince = now;
                        }
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

        final CheckBox demo = check(box, "Modo demostración (sin PS5)", "demo", false);

        section(box, "Qué te dice el ingeniero (también por voz con RAD)", pad);
        final CheckBox voz = check(box, "Voz del ingeniero", "voz", true);
        final CheckBox tiempos = check(box, "Tiempo de cada vuelta", "tiempos", true);
        final CheckBox comb = check(box, "Combustible en cada vuelta (el plan y lo crítico siempre)", "combustible", true);
        final CheckBox mitad = check(box, "Delta a mitad de vuelta", "mitad", true);
        final CheckBox neu = check(box, "Neumáticos y motor", "neumaticos", true);
        final CheckBox cons = check(box, "Consejos por curva (contra tu mejor vuelta)", "consejos", true);

        final int car;
        synchronized (lock) { car = telemetry.carCode; }
        section(box, car != 0 ? "Este auto (código " + car + "): te lo recuerdo en la parrilla" : "Auto: entra a una carrera para guardar sus valores", pad);
        final EditText tcs = field(box, "TCS que te acomoda, ej. 2", prefs.getString("tcs_" + car, ""));
        final EditText bb = field(box, "Balance de frenos, ej. -1", prefs.getString("bb_" + car, ""));
        tcs.setEnabled(car != 0); bb.setEnabled(car != 0);

        final TrackDb.Track trk;
        synchronized (lock) { trk = engineer.track; }
        section(box, trk != null ? "Circuito actual (" + trk.label() + ", " + Math.round(trk.length) + " m)"
                : "Circuito: lo reconozco después de la primera vuelta", pad);
        final EditText trkName = field(box, "Nombre del circuito, ej. Suzuka", trk != null ? trk.name : "");
        trkName.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_WORDS);
        trkName.setEnabled(trk != null && !trk.builtin);

        section(box, "Voz", pad);
        final RadioGroup acentos = new RadioGroup(this);
        String ac = prefs.getString("acento", "es-CL");
        for (int i = 0; i < ACENTOS.length; i++) {
            RadioButton rb = new RadioButton(this);
            rb.setText(ACENTO_NOMBRE[i] + (available(ACENTOS[i]) ? "" : " (no instalada)"));
            rb.setId(2000 + i);
            acentos.addView(rb);
            if (ACENTOS[i].equals(ac)) acentos.check(rb.getId());
        }
        box.addView(acentos);
        final RadioGroup rapidez = new RadioGroup(this);
        rapidez.setOrientation(LinearLayout.HORIZONTAL);
        float rp = prefs.getFloat("rapidez", 1.1f);
        for (int i = 0; i < RAPIDEZ.length; i++) {
            RadioButton rb = new RadioButton(this);
            rb.setText(RAPIDEZ_NOMBRE[i]);
            rb.setId(3000 + i);
            rapidez.addView(rb);
            if (Math.abs(RAPIDEZ[i] - rp) < 0.01f) rapidez.check(rb.getId());
        }
        box.addView(rapidez);
        final CheckBox grave = check(box, "Voz más grave", "grave", true);

        TextView le = new TextView(this);
        le.setText("Motor de voz instalado:");
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

        final String oldIp = prefs.getString("ip", "");
        final boolean oldDemo = prefs.getBoolean("demo", false);
        AlertDialog dlg = new AlertDialog.Builder(this)
            .setTitle("Ingeniero GT7")
            .setView(scroll(box))
            .setPositiveButton("Guardar", null)
            .setNeutralButton("Probar voz", null)
            .setNegativeButton("Cerrar", null)
            .create();
        dlg.setOnShowListener(new DialogInterface.OnShowListener() {
            public void onShow(final DialogInterface di) {
                final AlertDialog a = (AlertDialog) di;
                a.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(new View.OnClickListener() {
                    public void onClick(View v) {   // prueba la voz elegida sin cerrar
                        if (!ttsReady) { Toast.makeText(MainActivity.this, "La voz aún no está lista", Toast.LENGTH_SHORT).show(); return; }
                        applyVoice(ACENTOS[Math.max(0, acentos.getCheckedRadioButtonId() - 2000)],
                            RAPIDEZ[Math.max(0, rapidez.getCheckedRadioButtonId() - 3000)], grave.isChecked());
                        HashMap<String, String> p = new HashMap<String, String>();
                        tts.speak("Radio OK. Te escucho fuerte y claro, vamos por esa carrera.", TextToSpeech.QUEUE_FLUSH, p);
                    }
                });
                a.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(new View.OnClickListener() {
                    public void onClick(View v) {
                        String acento = ACENTOS[Math.max(0, acentos.getCheckedRadioButtonId() - 2000)];
                        float rate = RAPIDEZ[Math.max(0, rapidez.getCheckedRadioButtonId() - 3000)];
                        SharedPreferences.Editor e = prefs.edit().putString("ip", ip.getText().toString().trim())
                            .putBoolean("voz", voz.isChecked()).putBoolean("tiempos", tiempos.isChecked())
                            .putBoolean("combustible", comb.isChecked()).putBoolean("mitad", mitad.isChecked())
                            .putBoolean("neumaticos", neu.isChecked()).putBoolean("consejos", cons.isChecked())
                            .putBoolean("demo", demo.isChecked()).putBoolean("grave", grave.isChecked())
                            .putString("acento", acento).putFloat("rapidez", rate);
                        if (car != 0) e.putString("tcs_" + car, tcs.getText().toString().trim()).putString("bb_" + car, bb.getText().toString().trim());
                        e.commit();
                        int sel = motores.getCheckedRadioButtonId() - 1000;
                        String nuevo = sel >= 0 && sel < pkgs.size() ? pkgs.get(sel) : "";
                        if (!nuevo.equals(prefs.getString("motor", "")) && nuevo.length() > 0) {
                            prefs.edit().putString("motor", nuevo).commit();
                            ttsReady = false;
                            tts.shutdown();
                            tts = new TextToSpeech(MainActivity.this, MainActivity.this, nuevo);
                        } else applyVoice(acento, rate, grave.isChecked());
                        boolean reconnect = !oldIp.equals(prefs.getString("ip", "")) || oldDemo != demo.isChecked();
                        synchronized (lock) {
                            if (trk != null && !trkName.getText().toString().trim().equals(trk.name)) engineer.renameTrack(trkName.getText().toString());
                            applyPrefs();
                            if (reconnect) { engineer.reset(); lastPacketAt = 0; }
                        }
                        if (reconnect) start();
                        a.dismiss();
                    }
                });
            }
        });
        dlg.show();
    }

    volatile int batteryPct = -1;
    volatile boolean charging;

    private String readRaw(int id) {
        try {
            java.io.InputStream in = getResources().openRawResource(id);
            java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            in.close();
            return out.toString("UTF-8");
        } catch (Exception e) { return ""; }
    }

    /** Circuitos aprendidos: se guardan en la memoria interna de la app. */
    private String readFile(String name) {
        try {
            java.io.FileInputStream in = openFileInput(name);
            java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            in.close();
            return out.toString("UTF-8");
        } catch (Exception e) { return ""; }
    }

    private void writeFile(String name, String data) {
        try {
            java.io.FileOutputStream o = openFileOutput(name, MODE_PRIVATE);
            o.write(data.getBytes("UTF-8"));
            o.close();
        } catch (Exception ignored) { }
    }

    private void section(LinearLayout box, String title, int pad) {
        TextView t = new TextView(this);
        t.setText(title);
        t.setTextColor(0xffffe34d);
        t.setPadding(0, pad, 0, pad / 4);
        box.addView(t);
    }

    private EditText field(LinearLayout box, String hint, String value) {
        EditText e = new EditText(this);
        e.setSingleLine(true);
        e.setHint(hint);
        e.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_SIGNED);
        e.setText(value);
        box.addView(e);
        return e;
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
