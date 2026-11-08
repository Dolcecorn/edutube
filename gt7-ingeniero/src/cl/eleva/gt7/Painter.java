package cl.eleva.gt7;

/** Primitivas de dibujo: en la tablet usa Canvas; en el computador, Java2D (para vistas previas). */
interface Painter {
    int LEFT = 0, CENTER = 1, RIGHT = 2;
    void rect(float l, float t, float r, float b, int argb);
    void round(float l, float t, float r, float b, float radius, int argb);
    void outline(float l, float t, float r, float b, float radius, float width, int argb);
    /** y es la línea base del texto. */
    void text(String s, float x, float y, float size, int argb, int align, boolean bold);
    float width(String s, float size, boolean bold);
}
