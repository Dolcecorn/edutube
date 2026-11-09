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
    interface SetupProvider { String reminder(int carCode); }
    SetupProvider setup;

    // funciones que el piloto puede prender/apagar por voz
    boolean lapCalls = true;     // tiempo al cerrar cada vuelta
    boolean fuelCalls = true;    // combustible en cada vuelta (el plan y lo crítico siempre se dicen)
    boolean midLapCalls = true;
    boolean tyreCalls = true;
    boolean coachCalls = true;
    final Coach coach = new Coach();
    private float tipSaidAt = -1000;

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


    private final float[] hotSince = new float[4];
    private boolean flagPending;
    private boolean startReminded;
    private int planState = -1;     // -1 sin plan, 0 llega sin parar, 1 hay que parar
    private int tyreMoments;        // bits de momentos clave ya avisados
    private float clock;      // segundos de carrera (sólo corre en pista y sin pausa)
    private float waterSaidAt = -1000;

    Engineer(Voice v) {
        voice = v;
        for (int i = 0; i < 4; i++) hotSince[i] = -1;
    }

    void reset() {
        prevLap = -1; prevPid = -1; lapObserved = false; lapDist = 0; coach.ref = null; coach.nc = 0; coach.startLap();
        fuelHistN = 0; fuelPerLapPct = 0; fuelLapsLeft = -1; lapsToGo = -1; myBestMs = -1; deltaValid = false;
        lapTimeS = 0; pending = false; raceFinished = false; prevFuel = -1; fuelCriticalLap = -1; midLapSaid = false;
        for (int i = 0; i < 4; i++) hotSince[i] = -1;
        tyreSaid = -1000; flagPending = false;
        startReminded = false; planState = -1; tyreMoments = 0; flagPending = false;
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
            if (t.lap == 1 && prevLap == 0 && !startReminded) raceStart(t);
            prevLap = t.lap;
        }

        if (running && t.lap > 0 && !raceFinished) {
            clock += dt;
            lapTimeS += dt;
            lapDist += t.speedMs * dt;
            String tip = coach.sample(t, lapTimeS, lapDist);
            updateDelta();
            if (tip != null && coachCalls && !pending && clock - tipSaidAt > 3f) { tipSaidAt = clock; say(tip, false); }
            trackFuel(t);
            checkTyres(t);
            checkWater(t);
        }
        if (pending) resolvePending(t);
        updateFuelEstimate(t);
    }

    private void startLap(Telemetry t, boolean sawTransition) {
        lapObserved = sawTransition;
        lapTimeS = 0; lapDist = 0; midLapSaid = false;
        coach.startLap();
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
        // lapStartLastLapMs conserva el valor de cuando empezó la vuelta: si el juego ya lo
        // cambió en este mismo paquete, resolvePending lo detecta de inmediato.
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
            boolean newBest = myBestMs < 0 || ms < myBestMs, first = myBestMs < 0;
            if (newBest) { myBestMs = ms; if (pendingObserved) coach.adoptLast(); }
            if (lapCalls) {
                sb.append("Vuelta ").append(pendingLap).append(": ").append(speakTime(ms)).append(". ");
                if (newBest && !first) sb.append("¡Mejor vuelta! ");
                else if (!newBest) {
                    String dl = speakDelta((ms - myBestMs) / 1000f);
                    sb.append(Character.toUpperCase(dl.charAt(0))).append(dl.substring(1)).append(" más lento que tu mejor. ");
                }
            } else if (newBest && !first) sb.append("Mejor vuelta, ").append(speakTime(ms)).append(". ");
        }
        if (flagPending) { flagPending = false; sb.append(FLAG); }
        else if (!raceFinished) {
            String plan = fuelPlan(t);
            if (plan != null) sb.append(plan).append(' ');
            else if (fuelCalls && fuelLapsLeft >= 0) sb.append(fuelSentence());
            if (tyreCalls && tyreKeyMoment(t)) sb.append(tyreShort(t)).append(' ');
            if (lapsToGo == 1) sb.append("Última vuelta, a fondo.");
            else if (lapsToGo == 2) sb.append("Quedan dos vueltas.");
        }
        String msg = sb.toString().trim();
        if (msg.length() > 0) say(msg, false);
    }

    /** Plan de combustible: se dice la primera vez que se puede calcular y cuando cambia. */
    private String fuelPlan(Telemetry t) {
        if (fuelLapsLeft < 0 || lapsToGo <= 0 || !t.hasFuel()) return null;
        boolean ok = fuelLapsLeft >= lapsToGo - lapFraction();
        int st = ok ? 0 : 1;
        if (st == planState) return null;
        boolean firstPlan = planState < 0;
        planState = st;
        if (ok) return (firstPlan ? "Plan de combustible: llegamos al final sin parar" : "Cambio de plan: ahora llegamos sin parar")
                + ", con margen de " + num1(fuelLapsLeft - (lapsToGo - lapFraction())) + " vueltas.";
        Plan pl = plan(t);
        String head = firstPlan ? "Plan de combustible: " : "Cambio de plan: ";
        if (pl != null && pl.stops >= 2) return head + pitReport(t);
        return head + "vamos a tener que parar a repostar. " + pitReport(t);
    }

    /** Momentos clave para hablar de neumáticos: tras la 1ª vuelta, a mitad de carrera, a 3 del final y en la vuelta de parada. */
    private boolean tyreKeyMoment(Telemetry t) {
        int bit = 0;
        if (pendingLap == 1) bit = 1;
        else if (t.totalLaps >= 6 && pendingLap == t.totalLaps / 2) bit = 2;
        else if (lapsToGo == 3) bit = 4;
        else if (planState == 1 && pitLap(t) == t.lap) bit = 8;
        if (bit == 0 || (tyreMoments & bit) != 0) return false;
        tyreMoments |= bit;
        return true;
    }

    String tyreShort(Telemetry t) {
        float[] c = t.tyreTemp;
        float mx = Math.max(Math.max(c[0], c[1]), Math.max(c[2], c[3]));
        float mn = Math.min(Math.min(c[0], c[1]), Math.min(c[2], c[3]));
        String st = mx > TYRE_HOT ? "Hay calor de más, cuídalos." : mn < 60 ? "Todavía fríos." : "En rango.";
        return "Neumáticos: delanteros " + Math.round(c[0]) + " y " + Math.round(c[1]) + ", traseros "
                + Math.round(c[2]) + " y " + Math.round(c[3]) + " grados. " + st;
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
            planState = -1;
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
        float len = coach.refLength();
        if (len <= 0) return 0;
        if (coach.mapIdx >= 0) return Math.min(1f, coach.ref.d[coach.mapIdx] / len);
        return Math.min(1f, lapDist / len);
    }

    private void updateDelta() {
        Coach.Trace r = coach.ref;
        int i = coach.mapIdx;
        if (r == null || i <= 0 || i >= r.n - 1 || !lapObserved || lapTimeS < 1f) { deltaValid = false; return; }
        deltaS = lapTimeS - r.t[i];
        deltaValid = true;
        if (midLapCalls && !midLapSaid && lapFraction() > 0.5f) {
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

    private static final String[] FIRST_LAP_TIPS = {
        "Primera vuelta: los neumáticos están fríos, frena un poco antes y no arriesgues en la curva uno.",
        "Primera vuelta: mucho tráfico, deja espacio en la primera frenada y busca ritmo de a poco.",
        "Primera vuelta: neumáticos fríos, suave con el acelerador a la salida de las curvas lentas.",
        "Primera vuelta: sobrevivir a la curva uno vale más que ganar un puesto ahí. Frena con margen."
    };
    private int tipSeed;

    /** Saludo al largar: TCS y balance de frenos guardados, y un consejo de primera vuelta. */
    private void raceStart(Telemetry t) {
        startReminded = true;
        StringBuilder sb = new StringBuilder("¡Luz verde, vamos! ");
        String r = setup != null ? setup.reminder(t.carCode) : null;
        if (r != null) sb.append(r).append(' ');
        else sb.append("Revisa el TCS y el balance de frenos; puedes guardar tus valores para este auto en SET. ");
        sb.append(FIRST_LAP_TIPS[((tipSeed++ + t.carCode + t.packetId) & 0x7fffffff) % FIRST_LAP_TIPS.length]);
        say(sb.toString(), true);
    }

    /** Plan de paradas por combustible. */
    static final class Plan {
        int stops;        // 0 = llega sin parar
        int pitLap = -1;  // última vuelta que alcanzas a cerrar antes de la 1ª parada (0 = ahora)
        float load;       // % a cargar en la 1ª parada
        float savePct;    // % de ahorro por vuelta que permite hacerlo con una sola parada (0 si no aplica)
    }

    /** Calcula el plan; null sin datos. */
    Plan plan(Telemetry t) {
        float add = fuelToAdd(t);
        if (add < 0) return null;
        Plan p = new Plan();
        if (add < 0.5f) return p;
        p.pitLap = pitLap(t);
        float rest = 1f - lapFraction();
        float lapsToPit = p.pitLap <= 0 ? 0 : (p.pitLap - t.lap) + rest;
        float atPit = Math.max(0, t.fuelPct() - fuelPerLapPct * lapsToPit);
        float space = 100f - atPit;                // lo que cabe en el estanque al parar
        if (add <= space) { p.stops = 1; p.load = add; return p; }
        p.load = space;
        p.stops = 1 + (int) Math.ceil((add - space) / 100f);
        float need = fuelPerLapPct * (lapsToGo - lapFraction() + 0.5f);
        float have = t.fuelPct() + space;
        float save = 100f * (1f - have / need);
        if (save > 0 && save <= 10f) p.savePct = save;
        return p;
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
                + " por ciento por vuelta. " + fuelSentence()).trim();
    }

    /** Última vuelta que alcanzas a completar con el combustible actual; -1 sin datos, 0 si no alcanzas a cerrar esta. */
    int pitLap(Telemetry t) {
        if (fuelLapsLeft < 0 || t.lap <= 0) return -1;
        float rest = 1f - lapFraction();             // lo que falta de la vuelta actual
        if (fuelLapsLeft < rest) return 0;
        return t.lap + (int) Math.floor(fuelLapsLeft - rest);
    }

    private static String when(int pl, int lap) {
        if (pl == 0) return "No alcanzas a cerrar esta vuelta, entra a boxes ahora. ";
        if (pl == lap) return "Entra a boxes al final de esta vuelta. ";
        if (pl > 0) return "Entra a boxes a más tardar al final de la vuelta " + pl + ". ";
        return "";
    }

    String pitReport(Telemetry t) {
        Plan p = plan(t);
        if (p == null) return fuelReport(t);
        if (p.stops == 0) return "No necesitas parar por combustible, llegas al final.";
        if (p.stops == 1)
            return when(p.pitLap, t.lap) + "Carga " + Math.round(p.load) + " por ciento de combustible para terminar.";
        if (p.savePct > 0)
            return "Con una parada no alcanza ni llenando el estanque. Ahorra " + Math.max(1, Math.round(p.savePct))
                    + " por ciento por vuelta y llenando el estanque en una sola parada llegas; si no, serán dos paradas. "
                    + when(p.pitLap, t.lap).replace("Entra a boxes", "La parada:").replace("No alcanzas", "Ojo, no alcanzas");
        return "Vamos a necesitar " + p.stops + " paradas. " + when(p.pitLap, t.lap).replace("Entra a boxes", "La primera")
                + "Llena el estanque.";
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
    static final String HELP = "Toca RAD y dime: activa o desactiva consejos, tiempos, combustible, neumáticos o delta. "
            + "También: activa todo, o no me digas nada. Y pregúntame cuándo entro a boxes, cuánta bencina queda, cómo voy o cuántas vueltas faltan.";

    /** Comandos para prender/apagar funciones. Devuelve la respuesta o null si no es un comando. */
    String command(String q) {
        boolean off = has(q, "desactiva", "apaga", "no me des", "no me digas", "silencia", "quita", "basta", "deja de", "callate", "sin consejo", "nada");
        boolean on = !off && has(q, "activa", "enciende", "prende", "dame consejo", "vuelve a", "todo");
        if (has(q, "ayuda", "comandos", "que puedo decir")) return HELP;
        if (!off && !on) return null;
        boolean all = has(q, "todo", "nada", "todas", "silencio");
        boolean any = false;
        StringBuilder what = new StringBuilder();
        if (all || has(q, "consejo", "curva", "mejorar", "frenada", "telemetria")) { coachCalls = on; any = true; what.append("consejos por curva, "); }
        if (all || has(q, "delta", "mitad")) { midLapCalls = on; any = true; what.append("delta a mitad de vuelta, "); }
        if (all || has(q, "neumatic", "goma", "rueda")) { tyreCalls = on; any = true; what.append("neumáticos, "); }
        if (all || has(q, "combustible", "bencina", "gasolina")) { fuelCalls = on; any = true; what.append("combustible, "); }
        if (all || has(q, "tiempo", "vuelta")) { lapCalls = on; any = true; what.append("tiempos de vuelta, "); }
        if (!any) return null;
        if (all && !on) return "Listo, me quedo callado. Sólo te aviso lo importante: plan de combustible, combustible crítico y bandera. Di activa todo para volver.";
        if (all) return "Listo, te doy todo: tiempos, delta, consejos, combustible y neumáticos.";
        String w = what.substring(0, what.length() - 2);
        int k = w.lastIndexOf(", ");
        boolean many = k >= 0;
        if (many) w = w.substring(0, k) + " y " + w.substring(k + 2);
        return "Listo, " + w + (on ? (many ? " activados." : " activado.") : (many ? " desactivados." : " desactivado."));
    }

    String answer(String question, Telemetry t) {
        String q = fold(question);
        String cmd = command(q);
        if (cmd != null) return cmd;
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
        return "No te entendí. " + HELP;
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
