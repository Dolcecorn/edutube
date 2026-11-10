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
    static final String FLAG = "Bandera a cuadros. Terminaste la carrera, buen trabajo. En diez segundos te doy el resumen.";

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
    final Dynamics dyn = new Dynamics();
    final Session session = new Session();
    int raceEnds;              // sube cuando sale el resumen final (la vista salta al análisis)
    String debriefText = "";
    final java.util.ArrayList<String> debriefList = new java.util.ArrayList<String>();
    static final long DEBRIEF_DELAY_MS = 10000;   // el resumen sale 10 s después de la bandera
    interface Clock { long now(); }
    Clock time = new Clock() { public long now() { return System.currentTimeMillis(); } };
    private long debriefAt;                       // 0 = no hay resumen pendiente
    private final java.util.ArrayList<String> nextDebrief = new java.util.ArrayList<String>();
    private boolean sessionStale;                 // la carrera anterior se borra recién al empezar otra

    // circuitos conocidos
    interface TrackSaver { void save(String data); }
    TrackSaver trackSaver;
    final TrackDb tracks = new TrackDb();
    TrackDb.Track track;                          // circuito actual (null = todavía no se sabe)

    // boxes
    boolean inPit;
    private float pitCond, pitExitCond, pitTime;
    private boolean pitStopped, pitRefuel, curLapPit, pendingPit, refuelSeen;
    private float refuelAcc;
    int stopsDone;                       // paradas en boxes hechas en esta carrera
    float pitLossS = -1;                 // tiempo que cuesta una parada (medido); -1 = sin medir
    float refuelRate = -1;               // % de estanque por segundo al repostar (medido)
    private float stopTime, pitFuelAdded;
    private int pitLapsMs, pitLapsN;
    private int strategyKey = -1;

    // última pasada por cada curva (para responder "¿cómo estuvo la curva 2?")
    private final int[] cLap = new int[Session.MAXC];
    private final float[] cGain = new float[Session.MAXC], cMin = new float[Session.MAXC];
    private final int[] cEv = new int[Session.MAXC];
    private final String[] cTip = new String[Session.MAXC];

    // sectores (tercios de la vuelta según la referencia)
    private int sector;
    private final float[] secT = new float[2];
    private float pendingS1 = -1, pendingS12 = -1;
    private final int[][] trendSaidLap = new int[4][Session.MAXC];
    private float lapMaxKmh, pendingMaxKmh, bestLapMaxKmh;
    private final int[] lapEvMask = new int[Session.MAXC];
    private final int[] lapEvWheels = new int[Session.MAXC];
    private float evSaidAt = -1000;
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
        lapMaxKmh = 0; bestLapMaxKmh = 0;
        // el historial y el resumen se mantienen a la vista hasta que empiece otra carrera
        if (!session.laps.isEmpty() || !session.events.isEmpty()) sessionStale = true;
        else { dyn.reset(); session.clear(); }
        track = null; coach.useSegments(null, null);
        inPit = false; pitCond = 0; pitExitCond = 0; curLapPit = false; pendingPit = false;
        stopsDone = 0; pitLossS = -1; pitLapsMs = 0; pitLapsN = 0; strategyKey = -1;
        java.util.Arrays.fill(cLap, 0);
        sector = 0; pendingS1 = -1; pendingS12 = -1;
        for (int[] a : trendSaidLap) java.util.Arrays.fill(a, -10);
    }

    /** Hay que llamarlo seguido (también cuando no llegan paquetes): dispara el resumen final a su hora. */
    void tick() {
        if (debriefAt > 0 && time.now() >= debriefAt) {
            debriefAt = 0;
            debriefList.clear();
            debriefList.addAll(nextDebrief);
            StringBuilder sb = new StringBuilder("Resumen de la carrera. ");
            for (String x : debriefList) sb.append(x).append(' ');
            debriefText = sb.toString().trim();
            say(debriefText, false);
            raceEnds++;
        }
    }

    boolean debriefPending() { return debriefAt > 0; }

    long lastMessageAt;

    private void say(String s, boolean urgent) {
        lastMessage = s;
        lastMessageAt = System.currentTimeMillis();
        if (voice != null) voice.say(s, urgent);
    }

    private Telemetry lastT;

    void onPacket(Telemetry t) {
        lastT = t;
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

        dyn.update(t, dt, running && t.lap > 0);
        if (running && t.lap > 0 && !raceFinished) {
            clock += dt;
            lapTimeS += dt;
            lapDist += t.speedMs * dt;
            if (t.kmh() > lapMaxKmh) lapMaxKmh = t.kmh();
            String tip = coach.sample(t, lapTimeS, lapDist);
            updatePit(t, dt);
            updateSectors();
            updateDelta();
            if (dyn.evType >= 0) onDynEvent(t);
            if (coach.evaluatedNow) {
                int c = coach.lastCorner;
                if (lapObserved && !curLapPit) session.cornerResult(c, coach.lastGain, coach.lastMinKmh);
                String ev = c < Session.MAXC ? eventTip(c) : null;
                if (ev != null) tip = "Curva " + (c + 1) + ": " + ev
                        + (coach.lastGain >= 0.12f ? " Perdiste " + speakDelta(coach.lastGain) + "." : "");
                if (c >= 0 && c < Session.MAXC && lapObserved) {
                    cLap[c] = t.lap; cGain[c] = coach.lastGain; cMin[c] = coach.lastMinKmh; cEv[c] = lapEvMask[c];
                    cTip[c] = tip;
                }
            }
            if (inPit || curLapPit) tip = null;     // vuelta con boxes: sin consejos de curva
            if (tip != null && coachCalls && !pending && clock - tipSaidAt > 3f) { tipSaidAt = clock; say(tip, false); }
            trackFuel(t);
            checkTyres(t);
            checkWater(t);
        }
        if (pending) resolvePending(t);
        updateFuelEstimate(t);
        tick();
    }

    private void onDynEvent(Telemetry t) {
        int c = coach.cornerNow();
        session.addEvent(t.lap, c, dyn.evType, dyn.evWheels, t.kmh(), t.posX, t.posZ);
        if (c >= 0 && c < Session.MAXC) {
            lapEvMask[c] |= 1 << dyn.evType;
            if (dyn.evType == Dynamics.LOCK) lapEvWheels[c] |= dyn.evWheels;
            return;   // se comenta al salir de la curva
        }
        // sobreviraje y subviraje sueltos no se comentan: sólo cuando se repiten (ver eventTip)
        if (dyn.evType == Dynamics.OVER || dyn.evType == Dynamics.UNDER) return;
        if (!coachCalls || pending || inPit || clock - evSaidAt < 8f) return;
        evSaidAt = clock;
        String m = dyn.evType == Dynamics.LOCK ? "Bloqueaste " + Dynamics.wheels(dyn.evWheels) + "."
                : dyn.evType == Dynamics.SPIN ? "Patinas, cuidado con el acelerador."
                : dyn.evType == Dynamics.OVER ? "Se te fue la cola, suave." : "Subviraje, el auto no dobla.";
        say(m, false);
    }

    /** Lo que pasó en la curva c en esta vuelta (bloqueo, trompo, etc.), o null. */
    private String eventTip(int c) {
        int m = lapEvMask[c];
        if (m == 0) return null;
        if ((m & (1 << Dynamics.LOCK)) != 0)
            return "bloqueaste " + Dynamics.wheels(lapEvWheels[c]) + ". Frena un poco menos fuerte al inicio o suelta antes el freno.";
        String tr = trendTip(c, Dynamics.OVER, m);
        if (tr != null) return tr;
        if ((m & (1 << Dynamics.SPIN)) != 0) return "patinaste a la salida. Dosifica el acelerador hasta enderezar el volante.";
        return trendTip(c, Dynamics.UNDER, m);
    }

    /**
     * Sobreviraje / subviraje: sólo se avisa cuando se repite en la misma curva (2 de las últimas
     * 3 vueltas) y no se dijo hace poco. Así no se comenta un caso aislado.
     */
    private String trendTip(int c, int type, int mask) {
        if ((mask & (1 << type)) == 0) return null;
        int n = session.lapsWith(type, c, 3);
        if (n < 2 || prevLap - trendSaidLap[type][c] < 3) return null;
        trendSaidLap[type][c] = prevLap;
        String rep = " (" + n + " de las últimas 3 vueltas).";
        if (type == Dynamics.OVER)
            return "se repite el sobreviraje, se te va la cola" + rep
                    + " Acelera más suave y más tarde en el vértice; si sigue, sube un punto el TCS.";
        return "se repite el subviraje, el auto no dobla" + rep
                + " Entra más lento y suelta el freno de a poco; si sigue, mueve el balance de frenos un punto hacia atrás.";
    }

    /** Tendencias activas de sobre/subviraje, para el informe en boxes. */
    private String trendSummary() {
        StringBuilder sb = new StringBuilder();
        String[] what = {null, null, "se te va la cola en la curva ", "subviraje en la curva "};
        for (int type = Dynamics.OVER; type <= Dynamics.UNDER; type++) {
            int w = -1, wn = 1;
            for (int c = 0; c < Session.MAXC; c++) { int n = session.lapsWith(type, c, 3); if (n > wn) { wn = n; w = c; } }
            if (w >= 0) sb.append(sb.length() == 0 ? "Tendencia: " : " y ").append(what[type]).append(w + 1);
        }
        if (sb.length() == 0) return "";
        return sb.append(". Si quieres, ajusta el TCS o el balance de frenos un punto. ").toString();
    }

    /** Bandera a cuadros: el resumen se arma ahora y se dice (y se muestra) 10 s después. */
    private void finishRace() {
        nextDebrief.clear();
        nextDebrief.addAll(session.debriefItems());
        debriefAt = time.now() + DEBRIEF_DELAY_MS;
        inPit = false;
    }

    // ---------------------------------------------------------------- boxes
    /**
     * GT7 no avisa cuándo entras a boxes. Se detecta así: cerca de la meta, fuera de la línea de tu
     * mejor vuelta (el pit lane va al lado de la recta) y lento, o detenido cerca de la meta,
     * o cuando sube el combustible (repostaje). Se sale al volver a la línea con velocidad.
     */
    private void updatePit(Telemetry t, float dt) {
        float kmh = t.kmh();
        float f = lapFraction();
        boolean hasRef = coach.ref != null && coach.offLine >= 0;
        boolean nearLine = f > 0.8f || f < 0.2f;
        if (!inPit) {
            boolean off = hasRef && nearLine && coach.offLine > 12f && kmh < 110f && kmh > 3f;
            boolean stopped = hasRef && nearLine && kmh < 3f && lapTimeS > 3f;
            if (off || stopped) pitCond += dt; else pitCond = 0;
            if (pitCond > (stopped ? 1.5f : 2.5f)) enterPit(t);
        } else {
            pitTime += dt;
            if (kmh < 3f) { pitStopped = true; stopTime += dt; }
            if (refuelAcc > pitFuelAdded) pitFuelAdded = refuelAcc;
            boolean back = hasRef ? (coach.offLine < 6f && kmh > 60f) || kmh > 140f : kmh > 80f;
            if (back) pitExitCond += dt; else pitExitCond = 0;
            if (pitExitCond > 2f || (pitTime > 120f && kmh > 100f)) exitPit(t);
        }
    }

    private void enterPit(Telemetry t) {
        inPit = true; pitCond = 0; pitExitCond = 0; pitTime = 0; pitStopped = false; pitRefuel = false;
        stopTime = 0; pitFuelAdded = 0;
        curLapPit = true;
        say(pitInfo(t), false);
    }

    private void exitPit(Telemetry t) {
        inPit = false; pitExitCond = 0; curLapPit = true;
        if (pitStopped || pitRefuel) stopsDone++;
        if (pitRefuel && pitFuelAdded > 3f && stopTime > 1f) refuelRate = pitFuelAdded / stopTime;
        planState = -1;            // el plan se rehace con lo que cargaste
        StringBuilder sb = new StringBuilder("Saliendo de boxes");
        sb.append(stopsDone > 0 ? ", parada " + stopsDone + " lista. " : ". ");
        float mn = Math.min(Math.min(t.tyreTemp[0], t.tyreTemp[1]), Math.min(t.tyreTemp[2], t.tyreTemp[3]));
        if (pitStopped && mn < 70f)
            sb.append("Neumáticos fríos: frena un poco antes y acelera suave las primeras curvas hasta que tomen temperatura. ");
        else sb.append("Vamos, a buscar ritmo. ");
        if (pitRefuel && fuelLapsLeft >= 0 && lapsToGo > 0) {
            String pl = fuelPlan(lastT != null ? lastT : t);
            if (pl != null) sb.append(pl).append(' ');
        }
        say(sb.toString().trim(), false);
    }

    /** Lo que sirve saber mientras estás detenido en boxes. */
    String pitInfo(Telemetry t) {
        StringBuilder sb = new StringBuilder("Entrando a boxes. ");
        sb.append(pitFuel(t));
        int n = 0; long sum = 0;
        for (Session.Lap l : session.laps) if (l.ms > 0 && !l.pit && l.lap > 1) { n++; sum += l.ms; }
        if (myBestMs > 0) {
            sb.append("Tu mejor: ").append(speakTime(myBestMs));
            if (n >= 2) sb.append(", tu promedio ").append(speakTime((int) (sum / n)));
            sb.append(". ");
        }
        int ideal = session.idealMs();
        Session.Lap b = session.best();
        if (ideal > 0 && b != null && b.ms - ideal >= 100) {
            sb.append("Juntando tus mejores sectores tienes ").append(speakDelta((b.ms - ideal) / 1000f)).append(" más");
            int ws = session.weakSector();
            if (ws >= 0) sb.append(", sobre todo en el sector ").append(ws + 1);
            sb.append(". ");
        }
        int[] w = session.worstCorners(2);
        if (w.length > 0) {
            sb.append("Al salir, foco en la curva ").append(w[0] + 1);
            if (w.length > 1) sb.append(" y la ").append(w[1] + 1);
            sb.append(": ahí pierdes ").append(speakDelta(session.avgLoss(w[0])));
            if (w.length > 1) sb.append(" y ").append(speakDelta(session.avgLoss(w[1])));
            sb.append(" por vuelta. ");
        }
        sb.append(trendSummary());
        float mx = Math.max(Math.max(t.tyreTemp[0], t.tyreTemp[1]), Math.max(t.tyreTemp[2], t.tyreTemp[3]));
        if (mx > TYRE_HOT) sb.append("Los neumáticos venían sobre ").append(Math.round(mx)).append(" grados: cuida la entrada a las curvas. ");
        return sb.toString().trim();
    }

    /** Lo primero en boxes: cuánto combustible cargar en esta parada. */
    private String pitFuel(Telemetry t) {
        if (!t.hasFuel()) return "";
        if (fuelPerLapPct <= 0 || lapsToGo <= 0) return "Todavía no tengo el consumo para decirte cuánto cargar. ";
        float add = fuelToAdd(t);
        if (add < 0.5f) return "Combustible: no necesitas cargar, llegas al final. ";
        if (t.fuelPct() + add <= 100f) {
            String s = "Combustible: carga " + Math.round(add) + " por ciento y llegas al final";
            if (refuelRate > 0 && t.fuelPct() + add < 95f) s += "; no llenes, cada 10 por ciento de más son " + num1(10f / refuelRate) + " segundos parado";
            return s + ". ";
        }
        float after = add - (100f - t.fuelPct());
        int more = (int) Math.ceil(after / 100f);
        String s = "Combustible: llena el estanque. Aun así te quedará" + (more == 1 ? " una parada más" : "n " + more + " paradas más") + ". ";
        String st = saveAdvice(t, more);
        return st != null ? s + st : s;
    }

    // ---------------------------------------------------------------- estrategia
    private float avgCleanLapS() {
        int n = 0; long sum = 0;
        for (Session.Lap l : session.laps) if (l.ms > 0 && !l.pit && l.lap > 1) { n++; sum += l.ms; }
        if (n > 0) return sum / (float) n / 1000f;
        return myBestMs > 0 ? myBestMs / 1000f : 90f;
    }

    /** Las 2 curvas a las que llegas más rápido: donde el lift and coast ahorra más. */
    private String liftCorners() {
        Coach c = coach;
        if (c.ref == null || c.nc == 0) return "las frenadas desde más velocidad";
        int a = -1, b = -1;
        for (int k = 0; k < c.nc; k++) {
            if (c.cBrake[k] < 0) continue;
            float v = c.ref.v[c.cBrake[k]];
            if (a < 0 || v > c.ref.v[c.cBrake[a]]) { b = a; a = k; }
            else if (b < 0 || v > c.ref.v[c.cBrake[b]]) b = k;
        }
        if (a < 0) return "las frenadas desde más velocidad";
        return b < 0 ? "la curva " + (a + 1) : "las curvas " + (a + 1) + " y " + (b + 1);
    }

    private String technique(float save) {
        String lc = "lift and coast: suelta el acelerador unos 50 a 80 metros antes de frenar en " + liftCorners();
        if (save <= 4f) return lc + ".";
        if (save <= 8f) return lc + ", y cambio corto: pasa de marcha unas 800 revoluciones antes del corte.";
        return "baja el mapa de combustible un par de niveles en el menú del volante, más " + lc
                + ". Te confirmo en la vuelta siguiente si alcanza.";
    }

    /**
     * ¿Conviene ahorrar para hacer una parada menos? Compara lo que se pierde en pista ahorrando
     * (estimado: 10 % menos de consumo cuesta ~0,8 % del tiempo de vuelta) con lo que cuesta una parada.
     * Devuelve el consejo, o null si no aplica.
     */
    private String saveAdvice(Telemetry t, int stopsLeft) {
        if (stopsLeft <= 0) return null;
        float lapsLeft = lapsToGo - lapFraction();
        float need = fuelPerLapPct * (lapsLeft + 0.5f);
        float available = (inPit ? 100f : t.fuelPct()) + (stopsLeft - 1) * 100f;
        float save = 100f * (1f - available / need);
        if (save <= 0 || save > 15f) return null;
        float lap = avgCleanLapS();
        float cost = lap * save / 100f * 0.08f * lapsLeft;
        float loss = pitLossS > 0 ? pitLossS : 25f;
        String parada = stopsLeft == 1 ? "llegas sin otra parada" : "te ahorras una parada";
        if (cost < loss * 0.9f)
            return "Estrategia: si ahorras " + Math.max(1, Math.round(save)) + " por ciento por vuelta " + parada
                    + ". Pierdes " + (cost < 1f ? "casi nada" : "unos " + Math.round(cost) + " segundos") + " en pista y ganas unos " + Math.round(loss)
                    + (pitLossS > 0 ? "" : " estimados") + " de boxes. Cómo: " + technique(save) + " ";
        return "Ahorrar para evitar la parada no conviene: costaría unos " + Math.round(cost) + " segundos y la parada "
                + Math.round(loss) + ". Ve a fondo. ";
    }

    /** Estrategia completa en vivo (también responde a "¿qué estrategia?"). */
    String strategy(Telemetry t) {
        if (!t.hasFuel()) return "Este auto no gasta combustible en esta carrera: ve a fondo.";
        if (fuelPerLapPct <= 0 || lapsToGo <= 0) return "Necesito una vuelta completa y una carrera con vueltas definidas para calcular la estrategia.";
        Plan p = plan(t);
        if (p == null) return fuelReport(t);
        float lapsLeft = lapsToGo - lapFraction();
        if (p.stops == 0) {
            float margin = fuelLapsLeft - lapsLeft;
            if (margin > 1.5f) return "Llegas sin parar y te sobran " + num1(margin) + " vueltas de combustible. Si vas con mapa de ahorro, súbelo a 1 y ataca.";
            if (margin < 0.3f) return "Llegas sin parar pero muy justo. Para tener margen: " + technique(3f);
            return "Llegas sin parar con " + num1(margin) + " vueltas de margen. Ve a fondo.";
        }
        StringBuilder sb = new StringBuilder();
        if (p.stops == 1) sb.append(stopsDone > 0 ? "Te queda una parada más. " : "Plan: una parada. ");
        sb.append(pitReport(t)).append(' ');
        if (p.savePct > 0) return sb.append("Cómo ahorrar: ").append(technique(p.savePct)).toString().trim();
        String sv = saveAdvice(t, p.stops);
        if (sv != null) sb.append(sv);
        else if (p.stops == 1) sb.append("Carga sólo lo necesario: parada más corta y auto más liviano.");
        return sb.toString().trim();
    }

    /** Se habla al cerrar la vuelta sólo cuando cambia la recomendación. */
    private String strategyUpdate(Telemetry t) {
        if (!t.hasFuel() || fuelPerLapPct <= 0 || lapsToGo <= 1) return null;
        Plan p = plan(t);
        if (p == null || p.stops == 0) return null;
        String sv = p.savePct > 0 ? "Para hacer una sola parada: " + technique(p.savePct) : saveAdvice(t, p.stops);
        int key = p.stops * 10 + (p.savePct > 0 ? 3 : sv == null ? 0 : sv.startsWith("Estrategia") ? 1 : 2);
        if (key == strategyKey) return null;
        strategyKey = key;
        return sv;
    }

    // ---------------------------------------------------------------- preguntas sobre curvas y sectores
    private static final String[] NUM = {"cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
            "once", "doce", "trece", "catorce", "quince", "dieciseis", "diecisiete", "dieciocho", "diecinueve", "veinte"};

    /** Número que viene después de la palabra (dígitos o en palabras); -1 si no hay. */
    static int numberAfter(String q, String word) {
        int i = q.indexOf(word);
        if (i < 0) return -1;
        String rest = q.substring(i + word.length()).trim().replaceAll("^(numero|n°|nº|#)\\s*", "");
        String[] tok = rest.split("[^a-z0-9]+");
        if (tok.length == 0 || tok[0].length() == 0) return -1;
        String w = tok[0];
        if (w.matches("\\d+")) return Integer.parseInt(w);
        if (w.equals("una") || w.equals("primera") || w.equals("primer")) return 1;
        if (w.equals("segunda")) return 2;
        if (w.equals("tercera") || w.equals("tercer")) return 3;
        if (w.equals("veinti") && tok.length > 1) { int u = java.util.Arrays.asList(NUM).indexOf(tok[1]); return u > 0 ? 20 + u : 20; }
        if (w.startsWith("veinti")) { int u = java.util.Arrays.asList(NUM).indexOf(w.substring(6)); return u > 0 ? 20 + u : -1; }
        int k = java.util.Arrays.asList(NUM).indexOf(w);
        return k;
    }

    String cornerReport(int n) {
        int c = n - 1;
        if (coach.nc == 0) return "Todavía no tengo curvas: necesito una vuelta completa.";
        if (c < 0 || c >= coach.nc || c >= Session.MAXC) return "Este circuito tiene " + coach.nc + " curvas; pregúntame de la 1 a la " + coach.nc + ".";
        if (cLap[c] == 0) return "Todavía no pasas por la curva " + n + " con una vuelta de referencia.";
        StringBuilder sb = new StringBuilder("Curva " + n + " en la vuelta " + cLap[c] + ": ");
        if (Math.abs(cGain[c]) < 0.05f) sb.append("igual que en tu mejor vuelta");
        else sb.append(cGain[c] > 0 ? "perdiste " : "ganaste ").append(speakDelta(Math.abs(cGain[c]))).append(" contra tu mejor vuelta");
        if (cMin[c] > 0 && coach.cMinV[c] > 0) {
            int dv = Math.round(cMin[c] - coach.cMinV[c]);
            sb.append(", vértice a ").append(Math.round(cMin[c])).append(" kilómetros por hora");
            if (Math.abs(dv) >= 2) sb.append(", ").append(Math.abs(dv)).append(dv > 0 ? " más" : " menos").append(" que en tu mejor");
        }
        sb.append(". ");
        int m = cEv[c];
        if ((m & (1 << Dynamics.LOCK)) != 0) sb.append("Bloqueaste. ");
        if ((m & (1 << Dynamics.SPIN)) != 0) sb.append("Patinaste a la salida. ");
        if ((m & (1 << Dynamics.OVER)) != 0) sb.append("Se te fue la cola. ");
        if ((m & (1 << Dynamics.UNDER)) != 0) sb.append("El auto no dobló. ");
        if (cTip[c] != null) {
            String tip = cTip[c];
            int k = tip.indexOf(": ");
            if (tip.startsWith("Curva") && k > 0) tip = tip.substring(k + 2);
            String lo = fold(tip);
            if (!lo.startsWith("perdiste") && !lo.startsWith("ganaste")) sb.append("Consejo: ").append(tip);
            else if (cGain[c] < 0.1f) sb.append("Así está bien.");
        } else if (cGain[c] < 0.1f) sb.append("Así está bien.");
        float avg = session.avgLoss(c);
        if (session.lossN[c] >= 2 && avg >= 0.1f) sb.append(" En promedio pierdes ").append(speakDelta(avg)).append(" ahí.");
        return sb.toString().trim();
    }

    String sectorReport(int n) {
        if (n < 1 || n > 3) return "Hay 3 sectores: pregúntame por el 1, el 2 o el 3.";
        Session.Lap last = null;
        for (int i = session.laps.size() - 1; i >= 0; i--) { Session.Lap l = session.laps.get(i); if (l.s1 > 0) { last = l; break; } }
        if (last == null) return "Todavía no tengo sectores: necesito dos vueltas completas.";
        int v = n == 1 ? last.s1 : n == 2 ? last.s2 : last.s3, b = session.bestSector(n - 1);
        String s = "Sector " + n + " en la vuelta " + last.lap + ": " + speakTime(v);
        if (b > 0 && v > b) s += ", " + speakDelta((v - b) / 1000f) + " más lento que tu mejor sector";
        else if (b > 0) s += ", tu mejor sector";
        return s + ".";
    }

    String weakReport() {
        int[] w = session.worstCorners(3);
        if (w.length == 0) return "Todavía no veo curvas donde pierdas tiempo claro.";
        StringBuilder sb = new StringBuilder("Donde más pierdes: ");
        for (int k = 0; k < w.length; k++)
            sb.append(k == 0 ? "" : k == w.length - 1 ? " y " : ", ").append("curva ").append(w[k] + 1)
              .append(", ").append(speakDelta(session.avgLoss(w[k])));
        sb.append(" por vuelta.");
        int ws = session.weakSector();
        if (ws >= 0) sb.append(" El sector más flojo es el ").append(ws + 1).append(".");
        return sb.toString();
    }

    String idealReport() {
        int ideal = session.idealMs();
        if (ideal <= 0 || myBestMs <= 0) return "Necesito un par de vueltas completas para la vuelta ideal.";
        return "Tu vuelta ideal es " + speakTime(ideal) + ", " + speakDelta(Math.max(0, myBestMs - ideal) / 1000f) + " menos que tu mejor.";
    }

    // ---------------------------------------------------------------- sectores
    private void updateSectors() {
        if (!lapObserved || coach.ref == null || lapTimeS < 3f) return;
        float f = lapFraction();
        if (sector == 0 && f >= 1f / 3f && f < 0.6f) { secT[0] = lapTimeS; sector = 1; }
        else if (sector == 1 && f >= 2f / 3f && f < 0.95f) { secT[1] = lapTimeS; sector = 2; }
    }

    // ---------------------------------------------------------------- circuitos
    /** Tras la primera vuelta: compara la forma con los circuitos guardados. */
    private String recognizeTrack() {
        if (coach.ref == null || coach.nc == 0) return "";
        TrackDb.Track m = tracks.match(coach.ref);
        if (m != null && m.builtin) {
            track = m;
            coach.useTrack(m.ax, m.az, m.turns);
            // deja fijas las curvas encontradas: con cada mejor vuelta no se vuelve a buscar (es pesado en la tablet)
            float[][] sg = coach.segments();
            coach.useSegments(sg[0], sg[1]);
            session.trackName = m.name;
            return "Circuito reconocido: " + m.name + ". Numeré " + coach.nc + (coach.nc == 1 ? " curva" : " curvas")
                    + (coach.nc == m.turns ? ", igual que el juego. " : "; el juego cuenta " + m.turns + ". ");
        }
        if (m != null) {
            track = m;
            coach.useSegments(m.cs, m.ce);
            session.trackName = m.label();
            return "Circuito reconocido: " + m.label() + ". Uso la misma numeración de curvas de siempre, " + coach.nc + " curvas. ";
        }
        float[][] sg = coach.segments();
        track = tracks.add(coach.ref, sg[0], sg[1]);
        coach.useSegments(sg[0], sg[1]);     // la numeración queda fija el resto de la carrera
        session.trackName = track.label();
        saveTracks();
        return "Circuito nuevo, lo guardé como " + track.label() + " con " + coach.nc + " curvas. Puedes ponerle nombre en SET. ";
    }

    void renameTrack(String name) {
        if (track == null || name == null || track.builtin) return;
        track.name = name.trim();
        session.trackName = track.label();
        saveTracks();
    }

    private void saveTracks() { if (trackSaver != null) trackSaver.save(tracks.serialize()); }

    private void startLap(Telemetry t, boolean sawTransition) {
        java.util.Arrays.fill(lapEvMask, 0);
        java.util.Arrays.fill(lapEvWheels, 0);
        if (sessionStale) {   // empieza otra carrera: ahora sí se borra la anterior
            sessionStale = false;
            session.clear(); dyn.reset();
            if (debriefAt == 0) { debriefText = ""; debriefList.clear(); }
        }
        curLapPit = inPit;
        sector = 0;
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
                else { say(FLAG, false); finishRace(); }
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
        pendingMaxKmh = lapMaxKmh;
        pendingPit = curLapPit;
        pendingS1 = sector >= 1 ? secT[0] : -1;
        pendingS12 = sector >= 2 ? secT[1] : -1;
        lapMaxKmh = 0;
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
        if (ms > 0 || pendingObserved) {
            Session.Lap sl = session.addLap(pendingLap, ms, pendingMaxKmh, pendingObserved && pendingFuelUsed > 0 ? pendingFuelUsed : -1);
            sl.pit = pendingPit;
            if (pendingPit && ms > 0) { pitLapsMs += ms; pitLapsN++; }
            else if (!pendingPit && pitLapsN > 0) {
                float loss = pitLapsMs / 1000f - pitLapsN * avgCleanLapS();
                if (loss > 5f && loss < 200f) pitLossS = loss;
                pitLapsMs = 0; pitLapsN = 0;
            }
            if (ms > 0 && pendingS1 > 0 && pendingS12 > pendingS1) {
                int a = Math.round(pendingS1 * 1000), ab = Math.round(pendingS12 * 1000);
                if (ms - ab > 0) { sl.s1 = a; sl.s2 = ab - a; sl.s3 = ms - ab; }
            }
        }
        String trackMsg = "";
        if (ms > 0) {
            boolean newBest = myBestMs < 0 || ms < myBestMs, first = myBestMs < 0;
            if (newBest) {
                myBestMs = ms;
                if (pendingObserved) { coach.adoptLast(); if (track == null) trackMsg = recognizeTrack(); }
                bestLapMaxKmh = pendingMaxKmh;
            }
            if (pendingPit && lapCalls) {
                sb.append("Vuelta ").append(pendingLap).append(" con boxes: ").append(speakTime(ms)).append(". ");
            } else if (lapCalls) {
                sb.append("Vuelta ").append(pendingLap).append(": ").append(speakTime(ms)).append(". ");
                if (newBest && !first) sb.append("¡Mejor vuelta! ");
                else if (!newBest) {
                    String dl = speakDelta((ms - myBestMs) / 1000f);
                    sb.append(Character.toUpperCase(dl.charAt(0))).append(dl.substring(1)).append(" más lento que tu mejor. ");
                    if (bestLapMaxKmh > 0 && pendingMaxKmh > 0 && pendingMaxKmh < bestLapMaxKmh - 3)
                        sb.append("Velocidad máxima ").append(Math.round(pendingMaxKmh)).append(", ")
                          .append(Math.round(bestLapMaxKmh - pendingMaxKmh)).append(" menos que en tu mejor vuelta: sal más rápido de la curva antes de la recta. ");
                }
            } else if (newBest && !first) sb.append("Mejor vuelta, ").append(speakTime(ms)).append(". ");
        }
        sb.append(trackMsg);
        boolean endNow = false;
        if (flagPending) { flagPending = false; sb.append(FLAG); endNow = true; }
        else if (!raceFinished) {
            String plan = fuelPlan(t);
            if (plan != null) sb.append(plan).append(' ');
            else if (fuelCalls && fuelLapsLeft >= 0) sb.append(fuelSentence());
            String stg = pendingPit ? null : strategyUpdate(t);
            if (stg != null && pendingLap >= 2) sb.append(stg).append(' ');
            if (tyreCalls && tyreKeyMoment(t)) sb.append(tyreShort(t)).append(' ');
            if (lapsToGo == 1) sb.append("Última vuelta, a fondo.");
            else if (lapsToGo == 2) sb.append("Quedan dos vueltas.");
        }
        String msg = sb.toString().trim();
        if (msg.length() > 0) say(msg, false);
        if (endNow) finishRace();
    }

    /** Plan de combustible: se dice la primera vez que se puede calcular y cuando cambia. */
    private String fuelPlan(Telemetry t) {
        if (fuelLapsLeft < 0 || lapsToGo <= 0 || !t.hasFuel()) return null;
        boolean ok = fuelLapsLeft >= lapsToGo - lapFraction();
        int st = ok ? 0 : 1;
        if (st == planState) return null;
        boolean firstPlan = planState < 0;
        planState = st;
        boolean after = firstPlan && stopsDone > 0;   // plan nuevo justo después de una parada
        if (ok) return (after ? "Con lo que cargaste llegas al final sin parar" : firstPlan ? "Plan de combustible: llegamos al final sin parar" : "Cambio de plan: ahora llegamos sin parar")
                + ", con margen de " + num1(fuelLapsLeft - (lapsToGo - lapFraction())) + " vueltas.";
        Plan pl = plan(t);
        String head = after ? "Con lo que cargaste te queda" + (pl != null && pl.stops >= 2 ? "n " + pl.stops + " paradas más. " : " una parada más. ")
                : firstPlan ? "Plan de combustible: " : "Cambio de plan: ";
        if (after) return head + pitReport(t);
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
        // el juego carga el combustible de a poco: se suma lo que va subiendo
        if (prevFuel >= 0 && f > prevFuel + 0.001f) refuelAcc += f - prevFuel;
        else if (prevFuel >= 0 && f < prevFuel - 0.001f) refuelAcc = 0;
        if (refuelAcc > 1.5f && !refuelSeen) {
            // repostaje en boxes: esta vuelta no sirve para medir consumo
            refuelSeen = true;
            lapFuelValid = false;
            planState = -1;
            if (!inPit && !raceFinished && t.lap > 0) enterPit(t);   // repostó: estás en boxes aunque no lo haya visto antes
            pitRefuel = true;
        }
        if (refuelAcc == 0) refuelSeen = false;
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
        if (midLapCalls && !midLapSaid && !curLapPit && lapFraction() > 0.5f) {
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
        return (stopsDone > 0 ? "Quedan " + p.stops + " paradas más. " : "Vamos a necesitar " + p.stops + " paradas. ") + when(p.pitLap, t.lap).replace("Entra a boxes", "La próxima")
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
            + "También: activa todo, o no me digas nada. Y pregúntame cómo estuvo la curva 2, cómo voy en el sector 1, dónde pierdo tiempo, "
            + "cuál es la estrategia, cuándo entro a boxes, cuánta bencina queda o cuántas vueltas faltan.";

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
        if (has(q, "curva")) {
            int n = numberAfter(q, "curva");
            if (n > 0) return cornerReport(n);
            if (has(q, "peor", "pierdo", "mas lenta", "mejorar")) return weakReport();
            return "¿Qué curva? Dime, por ejemplo: cómo estuvo la curva 2.";
        }
        if (has(q, "sector")) {
            int n = numberAfter(q, "sector");
            return n > 0 ? sectorReport(n) : weakReport();
        }
        if (has(q, "donde pierdo", "peor", "mejorar", "que mejoro", "donde mejoro")) return weakReport();
        if (has(q, "ideal")) return idealReport();
        if (has(q, "estrategia", "ahorr", "mapa", "lift", "cambio corto", "short", "conviene"))
            return strategy(t);
        if (has(q, "circuito", "pista")) return track != null ? "Estamos en " + track.label() + ", con " + coach.nc + " curvas." : "Todavía no reconozco el circuito: necesito la primera vuelta completa.";
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
