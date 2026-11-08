package cl.eleva.gt7;

import java.util.Locale;

/**
 * El "ingeniero de carreras": sigue la carrera paquete a paquete (tiempos de vuelta, delta contra la
 * mejor vuelta, consumo de combustible, temperaturas) y decide qué decirle al piloto y cuándo.
 * No depende de Android, así se puede probar en el computador.
 */
final class Engineer {
    interface Voice { void say(String text, boolean urgent); }

    static final float HZ = 59.94f;           // GT7 manda ~60 paquetes por segundo
    static final float TYRE_HOT = 100f;       // °C
    static final float WATER_HOT = 115f;      // °C
    static final String FLAG = "Bandera a cuadros. Terminaste la carrera, buen trabajo.";

    private final Voice voice;
    boolean midLapCalls = true;
    boolean tyreCalls = true;

    // ---- estado visible en el dashboard ----
    float lapTimeS;            // vuelta actual (medida por la app)
    boolean deltaValid;
    float deltaS;              // + más lento / - más rápido que la mejor vuelta
    float fuelPerLapPct;       // consumo medio por vuelta (% del estanque); 0 = sin datos
    float fuelLapsLeft = -1;   // vueltas que alcanza el combustible; -1 = sin datos
    int lapsToGo = -1;         // vueltas que faltan contando la actual; -1 = sin límite
    int myBestMs = -1;
    String lastMessage = "";
    boolean raceFinished;

    // ---- seguimiento interno ----
    private int prevLap = -1;
    private int prevPid = -1;
    private boolean lapObserved;       // vimos el inicio de esta vuelta
    private float lapDist;
    private float lapStartFuel;
    private boolean lapFuelValid;
    private int lapStartLastLapMs;
    private float prevFuel = -1;
    private final float[] fuelHist = new float[3];
    private int fuelHistN;
    private boolean midLapSaid;
    private int fuelCriticalLap = -1;

    // vuelta finalizada esperando el tiempo oficial del juego
    private boolean pending;
    private int pendingLap, pendingPid;
    private float pendingMeasuredS;
    private boolean pendingObserved;
    private float pendingFuelUsed;

    // trazas (distancia, tiempo) de la vuelta actual y de la mejor
    private float[] curD = new float[8192], curT = new float[8192];
    private int curN;
    private float[] refD, refT;
    private int refN;

    private final float[] hotSince = new float[4];
    private boolean flagPending;
    private float clock;      // segundos de carrera (sólo corre en pista y sin pausa)
    private float waterSaidAt = -1000;

    Engineer(Voice v) {
        voice = v;
        for (int i = 0; i < 4; i++) hotSince[i] = -1;
    }

    void reset() {
        prevLap = -1; prevPid = -1; lapObserved = false; lapDist = 0; curN = 0; refN = 0; refD = refT = null;
        fuelHistN = 0; fuelPerLapPct = 0; fuelLapsLeft = -1; lapsToGo = -1; myBestMs = -1; deltaValid = false;
        lapTimeS = 0; pending = false; raceFinished = false; prevFuel = -1; fuelCriticalLap = -1; midLapSaid = false;
        for (int i = 0; i < 4; i++) hotSince[i] = -1;
        tyreSaid = -1000; flagPending = false;
    }

    long lastMessageAt;

    private void say(String s, boolean urgent) {
        lastMessage = s;
        lastMessageAt = System.currentTimeMillis();
        if (voice != null) voice.say(s, urgent);
    }

    void onPacket(Telemetry t) {
        if (prevPid >= 0 && t.packetId == prevPid) return;
        float dt = prevPid < 0 ? 0 : (t.packetId - prevPid) / HZ;
        if (dt < 0 || dt > 2f) dt = 0;   // salto raro: no lo contamos
        prevPid = t.packetId;
        boolean running = t.onTrack() && !t.paused() && !t.loading();

        // ---- cambios de vuelta ----
        if (t.lap != prevLap) {
            if (prevLap > 0 && t.lap == prevLap + 1) {
                finishLap(t);
            } else if (t.lap < prevLap || t.lap == 0) {
                if (prevLap > 0) reset();
            }
            if (t.lap > 0) startLap(t, prevLap >= 0);
            prevLap = t.lap;
        }

        if (running && t.lap > 0 && !raceFinished) {
            clock += dt;
            lapTimeS += dt;
            lapDist += t.speedMs * dt;
            addSample(lapDist, lapTimeS);
            updateDelta();
            trackFuel(t);
            checkTyres(t);
            checkWater(t);
        }
        if (pending) resolvePending(t);
        updateFuelEstimate(t);
    }

    private void startLap(Telemetry t, boolean sawTransition) {
        lapObserved = sawTransition;
        lapTimeS = 0; lapDist = 0; curN = 0; midLapSaid = false;
        lapStartFuel = t.fuelPct(); lapFuelValid = t.hasFuel();
        lapStartLastLapMs = pending ? lapStartLastLapMs : t.lastLapMs;
        if (t.totalLaps > 0) {
            lapsToGo = t.totalLaps - t.lap + 1;
            if (lapsToGo <= 0 && !raceFinished) {
                raceFinished = true;
                if (pending) flagPending = true;   // se dice después del tiempo de la última vuelta
                else say(FLAG, false);
            }
        } else lapsToGo = -1;
    }

    private void finishLap(Telemetry t) {
        // si había una vuelta pendiente sin tiempo oficial, se resuelve con lo medido
        if (pending) announce(t, -1);
        pending = true;
        pendingLap = prevLap;
        pendingPid = t.packetId;
        pendingMeasuredS = lapTimeS;
        pendingObserved = lapObserved;
        pendingFuelUsed = lapFuelValid ? lapStartFuel - t.fuelPct() : -1;
        // la traza de esta vuelta queda guardada en cur*, la copiamos si resulta ser la mejor
        lastTraceD = copy(curD, curN); lastTraceT = copy(curT, curN); lastTraceN = curN;
        // lapStartLastLapMs conserva el valor de cuando empezó la vuelta: si el juego ya lo
        // cambió en este mismo paquete, resolvePending lo detecta de inmediato.
    }

    private float[] lastTraceD, lastTraceT;
    private int lastTraceN;

    private static float[] copy(float[] a, int n) {
        float[] r = new float[Math.max(n, 1)];
        System.arraycopy(a, 0, r, 0, n);
        return r;
    }

    private void resolvePending(Telemetry t) {
        if (t.lastLapMs > 0 && t.lastLapMs != lapStartLastLapMs) announce(t, t.lastLapMs);
        else if (t.packetId - pendingPid > 90) announce(t, -1);
    }

    /** Fin de vuelta: arma un solo mensaje con tiempo, delta y combustible. */
    private void announce(Telemetry t, int gameMs) {
        pending = false;
        lapStartLastLapMs = t.lastLapMs;
        int ms = gameMs > 0 ? gameMs : (pendingObserved ? Math.round(pendingMeasuredS * 1000) : -1);

        // consumo
        if (pendingFuelUsed > 0.05f && pendingFuelUsed < 60f && pendingObserved) {
            if (fuelHistN < fuelHist.length) fuelHist[fuelHistN++] = pendingFuelUsed;
            else { System.arraycopy(fuelHist, 1, fuelHist, 0, fuelHist.length - 1); fuelHist[fuelHist.length - 1] = pendingFuelUsed; }
            float s = 0; for (int i = 0; i < fuelHistN; i++) s += fuelHist[i];
            fuelPerLapPct = s / fuelHistN;
        }
        updateFuelEstimate(t);

        StringBuilder sb = new StringBuilder();
        if (ms > 0) {
            sb.append("Vuelta ").append(pendingLap).append(": ").append(speakTime(ms)).append(". ");
            if (myBestMs < 0 || ms < myBestMs) {
                boolean first = myBestMs < 0;
                myBestMs = ms;
                if (pendingObserved && lastTraceN > 10) { refD = lastTraceD; refT = lastTraceT; refN = lastTraceN; }
                if (!first) sb.append("¡Mejor vuelta! ");
            } else {
                sb.append(speakDelta((ms - myBestMs) / 1000f)).append(" más lento que tu mejor. ");
            }
        }
        if (flagPending) { flagPending = false; sb.append(FLAG); }
        else if (raceFinished) { /* nada más que decir */ }
        else if (fuelLapsLeft >= 0) {
            sb.append(fuelSentence());
        }
        if (!raceFinished && lapsToGo == 1) sb.append("Última vuelta, a fondo.");
        else if (!raceFinished && lapsToGo == 2) sb.append("Quedan dos vueltas.");
        String msg = sb.toString().trim();
        if (msg.length() > 0) say(msg, false);
    }

    String fuelSentence() {
        if (fuelLapsLeft < 0) return "";
        String alc = "El combustible alcanza para " + num1(fuelLapsLeft) + (Math.abs(fuelLapsLeft - 1f) < 0.05f ? " vuelta" : " vueltas");
        if (lapsToGo <= 0) return alc + ". ";
        float margin = fuelLapsLeft - (lapsToGo - lapFraction());
        if (margin >= 0.3f) return alc + ", faltan " + lapsToGo + ". Vamos bien. ";
        if (margin >= 0f) return alc + ", faltan " + lapsToGo + ". Muy justo, cuida el consumo. ";
        // falta combustible: cuánto hay que ahorrar por vuelta para llegar
        float need = 100f * (1f - fuelLapsLeft / (lapsToGo - lapFraction()));
        if (need <= 25f)
            return alc + " y faltan " + lapsToGo + ". Ahorra " + Math.round(need) + " por ciento por vuelta o tendrás que parar. ";
        return alc + " y faltan " + lapsToGo + ". No llegas: planifica una parada en boxes. ";
    }

    private void trackFuel(Telemetry t) {
        if (!t.hasFuel()) return;
        float f = t.fuelPct();
        if (prevFuel >= 0 && f > prevFuel + 1f) {
            // repostaje en boxes: esta vuelta no sirve para medir consumo
            lapFuelValid = false;
            if (f - prevFuel > 3f) say("Carga de combustible registrada.", false);
        }
        prevFuel = f;
        // combustible crítico: no alcanza para terminar la vuelta siguiente
        if (fuelLapsLeft >= 0 && fuelLapsLeft < 1.1f && lapsToGo > 1
                && fuelLapsLeft < lapsToGo - lapFraction() && !pending && lapTimeS > 3f && fuelCriticalLap != t.lap) {
            fuelCriticalLap = t.lap;
            say("Combustible crítico. Entra a boxes al final de esta vuelta.", true);
        }
    }

    private void updateFuelEstimate(Telemetry t) {
        if (fuelPerLapPct > 0.05f && t.hasFuel()) {
            fuelLapsLeft = Math.max(0, t.fuelPct() / fuelPerLapPct);
        } else fuelLapsLeft = -1;
    }

    /** Fracción recorrida de la vuelta según la vuelta de referencia (0 si no hay referencia). */
    float lapFraction() {
        if (refN < 2 || refD[refN - 1] <= 0) return 0;
        return Math.min(1f, lapDist / refD[refN - 1]);
    }

    private void addSample(float d, float tm) {
        if (curN == curD.length) {
            float[] nd = new float[curN * 2], nt = new float[curN * 2];
            System.arraycopy(curD, 0, nd, 0, curN); System.arraycopy(curT, 0, nt, 0, curN);
            curD = nd; curT = nt;
        }
        curD[curN] = d; curT[curN] = tm; curN++;
    }

    private void updateDelta() {
        if (refN < 10 || !lapObserved || lapDist > refD[refN - 1] || lapTimeS < 1f) { deltaValid = false; return; }
        int lo = 0, hi = refN - 1;
        while (hi - lo > 1) { int m = (lo + hi) >>> 1; if (refD[m] < lapDist) lo = m; else hi = m; }
        float d0 = refD[lo], d1 = refD[hi];
        float tRef = d1 > d0 ? refT[lo] + (refT[hi] - refT[lo]) * (lapDist - d0) / (d1 - d0) : refT[lo];
        deltaS = lapTimeS - tRef;
        deltaValid = true;
        if (midLapCalls && !midLapSaid && lapDist > 0.5f * refD[refN - 1]) {
            midLapSaid = true;
            if (Math.abs(deltaS) < 0.05f) say("Mitad de vuelta, igual que tu mejor.", false);
            else say("Mitad de vuelta, " + speakDelta(Math.abs(deltaS)) + (deltaS > 0 ? " abajo." : " arriba, sigue así."), false);
        }
    }

    private static final String[] TYRE = {"delantero izquierdo", "delantero derecho", "trasero izquierdo", "trasero derecho"};

    private float tyreSaid = -1000;

    private void checkTyres(Telemetry t) {
        if (!tyreCalls) return;
        int worst = -1;
        for (int i = 0; i < 4; i++) {
            if (t.tyreTemp[i] > TYRE_HOT) {
                if (hotSince[i] < 0) hotSince[i] = clock;
                if (clock - hotSince[i] > 4f && (worst < 0 || t.tyreTemp[i] > t.tyreTemp[worst])) worst = i;
            } else hotSince[i] = -1;
        }
        // un aviso cada 90 s como máximo, para no saturar la radio
        if (worst < 0 || clock - tyreSaid < 90f) return;
        tyreSaid = clock;
        int pair = worst ^ 1;
        boolean both = hotSince[pair] >= 0 && clock - hotSince[pair] > 4f;
        String what = both ? (worst < 2 ? "Delanteros" : "Traseros") + " muy calientes"
                : "Neumático " + TYRE[worst] + " muy caliente";
        say(what + ", " + Math.round(t.tyreTemp[worst]) + " grados. Suaviza "
                + (worst < 2 ? "la entrada a las curvas." : "la aceleración."), false);
    }

    private void checkWater(Telemetry t) {
        if (t.waterTemp > WATER_HOT && clock - waterSaidAt > 90f) {
            waterSaidAt = clock;
            say("Temperatura del motor alta, " + Math.round(t.waterTemp) + " grados.", false);
        }
    }

    /** % de estanque que falta cargar para terminar (con media vuelta de margen); -1 sin datos. */
    float fuelToAdd(Telemetry t) {
        if (fuelPerLapPct <= 0 || lapsToGo <= 0 || !t.hasFuel()) return -1;
        float need = fuelPerLapPct * (lapsToGo - lapFraction() + 0.5f) - t.fuelPct();
        return Math.max(0, need);
    }

    String fuelReport(Telemetry t) {
        if (!t.hasFuel()) return "Este auto no gasta combustible en esta carrera.";
        if (fuelLapsLeft < 0) return "Combustible " + Math.round(t.fuelPct()) + " por ciento. Necesito una vuelta completa para calcular el consumo.";
        return ("Combustible " + Math.round(t.fuelPct()) + " por ciento, gastas " + num1(fuelPerLapPct)
                + " por vuelta. " + fuelSentence()).trim();
    }

    /** Última vuelta que alcanzas a completar con el combustible actual; -1 sin datos, 0 si no alcanzas a cerrar esta. */
    int pitLap(Telemetry t) {
        if (fuelLapsLeft < 0 || t.lap <= 0) return -1;
        float rest = 1f - lapFraction();             // lo que falta de la vuelta actual
        if (fuelLapsLeft < rest) return 0;
        return t.lap + (int) Math.floor(fuelLapsLeft - rest);
    }

    String pitReport(Telemetry t) {
        float add = fuelToAdd(t);
        if (add < 0) return fuelReport(t);
        if (add < 0.5f) return "No necesitas parar por combustible, llegas al final.";
        StringBuilder sb = new StringBuilder();
        int pl = pitLap(t);
        if (pl == 0) sb.append("No alcanzas a cerrar esta vuelta, entra a boxes ahora. ");
        else if (pl == t.lap) sb.append("Entra a boxes al final de esta vuelta. ");
        else if (pl > 0) sb.append("Entra a boxes a más tardar al final de la vuelta ").append(pl).append(". ");
        sb.append("Carga ").append(Math.round(add)).append(" por ciento de combustible para terminar.");
        return sb.toString();
    }

    static String fold(String s) {
        s = s.toLowerCase(Locale.US);
        String a = "áéíóúüñ", b = "aeiouun";
        for (int i = 0; i < a.length(); i++) s = s.replace(a.charAt(i), b.charAt(i));
        return s;
    }

    private static boolean has(String q, String... words) {
        for (String w : words) if (q.contains(w)) return true;
        return false;
    }

    /** Responde una pregunta hablada (texto reconocido). */
    String answer(String question, Telemetry t) {
        String q = fold(question);
        if (has(q, "adelante", "atras", "rival", "distancia", "paralelo", "posicion", "lugar", "acerca", "otro auto", "los autos"))
            return "No puedo ver a los otros autos: GT7 sólo me manda los datos de tu auto. Para eso mira el mapa y los espejos.";
        if (has(q, "clima", "lluvia", "llover", "llueve", "mojad", "tiempo atmosf"))
            return "GT7 no me manda el clima. Mira el radar de lluvia en la pantalla del juego.";
        if (has(q, "rapida de la carrera", "record", "de los demas", "del resto"))
            return "Sólo veo tus vueltas, no las de los demás. " + lapReport(t);
        if (has(q, "parar", "parada", "boxes", "box", "pits", "detener", "reposta", "cargar", "entrar"))
            return (has(q, "neumatic", "goma", "rueda", "llanta")
                    ? "GT7 no me manda el desgaste de los neumáticos, así que la parada te la calculo por combustible. " : "")
                    + pitReport(t);
        if (has(q, "combustible", "bencina", "gasolina", "nafta", "estanque", "consumo")) return fuelReport(t);
        if (has(q, "neumatic", "goma", "rueda", "llanta", "desgaste"))
            return (has(q, "desgaste", "cambiar") ? "El desgaste no viene en la telemetría, te doy las temperaturas. " : "") + tyreReport(t);
        if (has(q, "faltan", "cuantas vueltas", "que vuelta", "vuelta voy", "en que vuelta")) {
            if (t.lap <= 0) return "Todavía no empieza la carrera.";
            if (t.totalLaps <= 0) return "Vas en la vuelta " + t.lap + ", sin límite de vueltas.";
            return "Vas en la vuelta " + t.lap + " de " + t.totalLaps + ". Faltan " + Math.max(0, lapsToGo) + " contando esta.";
        }
        if (has(q, "motor", "agua", "aceite", "temperatura"))
            return "Agua " + Math.round(t.waterTemp) + " grados, aceite " + Math.round(t.oilTemp) + " grados"
                    + (t.waterTemp > WATER_HOT ? ". El motor está caliente." : ". Todo normal.");
        if (has(q, "vuelta", "tiempo", "mejor", "ultima", "delta", "rapid")) return lapReport(t);
        if (has(q, "como voy", "como vamos", "estado", "resumen", "como estoy")) return status(t);
        return "No te entendí. Pregúntame por combustible, boxes, neumáticos, tiempos o vueltas que faltan.";
    }

    String tyreReport(Telemetry t) {
        StringBuilder sb = new StringBuilder("Neumáticos: ");
        String[] n = {"delantero izquierdo ", "delantero derecho ", "trasero izquierdo ", "trasero derecho "};
        for (int i = 0; i < 4; i++) sb.append(n[i]).append(Math.round(t.tyreTemp[i])).append(i < 3 ? ", " : ". ");
        float mx = Math.max(Math.max(t.tyreTemp[0], t.tyreTemp[1]), Math.max(t.tyreTemp[2], t.tyreTemp[3]));
        float mn = Math.min(Math.min(t.tyreTemp[0], t.tyreTemp[1]), Math.min(t.tyreTemp[2], t.tyreTemp[3]));
        if (mx > TYRE_HOT) sb.append("Hay neumáticos sobrecalentados, baja el ritmo en curvas.");
        else if (mn < 60) sb.append("Todavía están fríos, caliéntalos.");
        else sb.append("Temperaturas en rango.");
        return sb.toString();
    }

    String lapReport(Telemetry t) {
        StringBuilder sb = new StringBuilder();
        if (t.lastLapMs > 0) sb.append("Última vuelta ").append(speakTime(t.lastLapMs)).append(". ");
        if (myBestMs > 0) sb.append("Tu mejor ").append(speakTime(myBestMs)).append(". ");
        if (deltaValid) sb.append(Math.abs(deltaS) < 0.05f ? "Ahora vas igual que tu mejor."
                : "Ahora vas " + speakDelta(Math.abs(deltaS)) + (deltaS > 0 ? " abajo." : " arriba."));
        if (sb.length() == 0) sb.append("Todavía no hay vueltas completas.");
        return sb.toString().trim();
    }

    /** Resumen a pedido (cuando el piloto toca la barra del ingeniero). */
    String status(Telemetry t) {
        StringBuilder sb = new StringBuilder();
        if (t.lap > 0) {
            sb.append("Vuelta ").append(t.lap);
            if (t.totalLaps > 0) sb.append(" de ").append(t.totalLaps);
            sb.append(". ");
        }
        if (myBestMs > 0) sb.append("Tu mejor: ").append(speakTime(myBestMs)).append(". ");
        if (deltaValid) sb.append(Math.abs(deltaS) < 0.05f ? "Vas igual que tu mejor. "
                : "Vas " + speakDelta(Math.abs(deltaS)) + (deltaS > 0 ? " abajo. " : " arriba. "));
        if (t.hasFuel()) {
            sb.append("Combustible ").append(Math.round(t.fuelPct())).append(" por ciento. ");
            if (fuelLapsLeft >= 0) sb.append(fuelSentence());
            else sb.append("Necesito una vuelta completa para calcular el consumo. ");
        }
        if (sb.length() == 0) sb.append("Sin datos de carrera todavía.");
        return sb.toString().trim();
    }

    // ---- números hablados en español ----
    static String speakTime(int ms) {
        int tenths = Math.round(ms / 100f);
        int min = tenths / 600;
        int sec = (tenths % 600) / 10;
        int d = tenths % 10;
        String s = sec + (d != 0 ? " coma " + d : "");
        if (min == 0) return s + " segundos";
        return min + (min == 1 ? " minuto " : " minutos ") + s;
    }

    static String speakDelta(float s) {
        int tenths = Math.round(Math.abs(s) * 10f);
        if (tenths == 0) return "menos de una décima";
        if (tenths < 10) return tenths == 1 ? "una décima" : tenths + " décimas";
        int whole = tenths / 10, d = tenths % 10;
        return whole + (d != 0 ? " coma " + d : "") + (tenths == 10 ? " segundo" : " segundos");
    }

    static String num1(float v) {
        float r = Math.round(v * 10f) / 10f;
        if (r == Math.floor(r)) return String.valueOf((int) r);
        return String.format(Locale.US, "%.1f", r).replace(".", " coma ");
    }

    static String clockText(float s) {
        if (s < 0) s = 0;
        int ms = Math.round(s * 1000);
        return String.format(Locale.US, "%d:%02d.%03d", ms / 60000, (ms / 1000) % 60, ms % 1000);
    }

    static String msText(int ms) { return ms > 0 ? clockText(ms / 1000f) : "--:--.---"; }
}
