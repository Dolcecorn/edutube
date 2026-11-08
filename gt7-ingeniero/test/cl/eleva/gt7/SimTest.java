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
                    "cuántas vueltas faltan", "cómo voy", "hola", "desactiva los consejos", "no me digas nada", "activa todo", "apaga el combustible y los neumáticos", "ayuda"};
                for (String q : qs) System.out.println("P: " + q + "\nR: " + eng.answer(q, t));
            }
        }
        System.out.println("paquetes inválidos: " + bad);
    }
}
