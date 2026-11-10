package cl.eleva.gt7;

public class SimTest {
    public static void main(String[] a) {
        // 1) Salsa20 contra vector de pycryptodome (se pasa por argumento en hex)
        if (a.length > 0) {
            byte[] data = new byte[100];
            byte[] nonce = {1, 2, 3, 4, 5, 6, 7, 8};
            Salsa20.xor(Telemetry.KEY, nonce, data, 100);
            StringBuilder sb = new StringBuilder();
            for (byte b : data) sb.append(String.format("%02x", b));
            System.out.println(sb.toString().equals(a[0]) ? "SALSA20 OK" : "SALSA20 FALLA " + sb);
        }
        // 2) carrera simulada completa
        Simulator sim = new Simulator();
        final float[] now = {0};
        Engineer eng = new Engineer(new Engineer.Voice() {
            public void say(String s, boolean urgent) {
                System.out.println(String.format("[%6.1fs]%s %s", now[0], urgent ? " !!" : "", s));
            }
        });
        eng.time = new Engineer.Clock() { public long now() { return Math.round(now[0] * 1000); } };
        eng.trackSaver = new Engineer.TrackSaver() { public void save(String d) { System.out.println("   [pistas guardadas: " + d.length() + " bytes]"); } };
        eng.setup = new Engineer.SetupProvider() { public String reminder(int car) { return "Antes de largar: TCS en 2 y balance de frenos en menos 1."; } };
        Telemetry t = new Telemetry();
        int bad = 0;
        for (int i = 0; i < 60 * 60 * 15; i++) {
            byte[] p = sim.next();
            if (!t.decrypt(p, p.length)) { bad++; continue; }
            now[0] = i / 59.94f;
            eng.onPacket(t);
            if (i % (60 * 40) == 0)
                System.out.println(String.format("   t=%.0f vuelta %d/%d %s delta=%s %.0fkm/h marcha %d rpm %.0f comb %.1f%% (%.1f vueltas) neum %.0f/%.0f/%.0f/%.0f",
                    now[0], t.lap, t.totalLaps, Engineer.clockText(eng.lapTimeS), eng.deltaValid ? String.format("%+.2f", eng.deltaS) : "-",
                    t.kmh(), t.gear, t.rpm, t.fuelPct(), eng.fuelLapsLeft, t.tyreTemp[0], t.tyreTemp[1], t.tyreTemp[2], t.tyreTemp[3]));
            if (i == 60 * 60 * 5) {
                System.out.println("ESTADO: " + eng.status(t));
                String[] qs = {"¿Cuándo tengo que entrar a boxes?", "a cuánto estoy del auto de adelante", "cuál es la vuelta rápida de la carrera",
                    "en qué vuelta debo parar a cambiar neumáticos", "cómo está el clima, viene lluvia", "cuánta bencina me queda",
                    "cuántas vueltas faltan", "cómo voy", "hola", "cómo estuvo la curva 2 en esta vuelta", "y la curva tres", "cómo voy en el sector dos", "cuál es la estrategia", "conviene ahorrar combustible", "dónde pierdo más tiempo", "en qué circuito estamos", "desactiva los consejos", "no me digas nada", "activa todo", "apaga el combustible y los neumáticos", "ayuda"};
                for (String q : qs) System.out.println("P: " + q + "\nR: " + eng.answer(q, t));
            }
        }
        System.out.println("paquetes inválidos: " + bad + "  curvas detectadas: " + eng.coach.nc + " vistas resumen: " + eng.raceEnds);
        for (String b : eng.debriefList) System.out.println("  • " + b);
        for (Session.Lap l : eng.session.laps) System.out.println(String.format("   V%d %s s1=%d s2=%d s3=%d pit=%b", l.lap, Engineer.msText(l.ms), l.s1, l.s2, l.s3, l.pit));
        System.out.println("ideal " + Engineer.msText(eng.session.idealMs()));
        // segunda carrera en el mismo circuito: debe reconocerlo
        Engineer e3 = new Engineer(new Engineer.Voice() { public void say(String s, boolean u) { if (s.contains("ircuito")) System.out.println("CARRERA 2: " + s); } });
        e3.tracks.load(eng.tracks.serialize());
        Simulator s3 = new Simulator(); s3.pitAt = 0;
        Telemetry t3 = new Telemetry();
        for (int i = 0; i < 60 * 60 * 3; i++) { byte[] p = s3.next(); t3.decrypt(p, p.length); e3.onPacket(t3); }
        System.out.println("CARRERA 2 curvas " + e3.coach.nc + " pista " + (e3.track != null ? e3.track.label() : "-"));
        for (float rate : new float[]{15.5f, 18f, 19.5f, 20.5f, 21.5f, 30f}) {
            Simulator s2 = new Simulator(rate);
            Engineer e2 = new Engineer(null);
            Telemetry t2 = new Telemetry();
            for (int i = 0; i < (int) (60 * 60 * 2.6f); i++) { byte[] p = s2.next(); t2.decrypt(p, p.length); e2.onPacket(t2); }
            System.out.println("CONSUMO " + rate + "%/v, vuelta " + t2.lap + ", comb " + Math.round(t2.fuelPct()) + "%: " + e2.pitReport(t2) + "\n   ESTRATEGIA: " + e2.strategy(t2));
        }
    }
}
