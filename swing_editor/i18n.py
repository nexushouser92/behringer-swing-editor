"""User-facing texts in Spanish and English, chosen from the Windows language."""
import locale

TEXTS = {
    "es": {
        "title": "Swing Editor · Proyecto no oficial",
        "heading": "Ajustes del Swing",
        "subheading": "Behringer Swing · Proyecto no oficial",
        "disclaimer": "Proyecto no oficial, sin relación con Behringer/Music Tribe.",
        "status_searching": "○   Buscando Swing…",
        "status_busy": "⚠   Swing en uso por otro programa",
        "port_busy": "Otro programa está usando el Swing (un DAW como Ableton, o Control Tribe). Ciérralo, o desactiva el Swing en las preferencias MIDI del DAW; el editor se conectará solo.",
        "status_reading": "●   Swing vinculado · leyendo ajustes…",
        "status_linked": "●   Swing vinculado",
        "status_writing": "●   Swing vinculado · aplicando cambios…",
        "status_written": "✓   Swing vinculado · cambios aplicados",
        "status_failed": "⚠   No se pudo aplicar · pulsa para reintentar",
        "open": "Abrir…",
        "save": "Guardar…",
        "undo_all": "Deshacer cambios",
        "daw_on": "Modo DAW",
        "daw_off": "Salir del modo DAW",
        "daw_on_confirm": (
            "El modo DAW prepara el Swing para usarlo con un DAW por USB:\n\n"
            "• Play, Stop y Rec por el canal 16 (no se mezclan con las notas)\n"
            "• Tira Mod en el CC 1 estándar\n"
            "• MIDI Thru apagado\n"
            "• Transposición solo desde USB\n"
            "• Velocidad lineal\n"
            "• Transporte solo por MIDI CC (sin MMC: un botón nunca actúa dos veces)\n"
            "• Hold mantiene las teclas (cada nota se suelta con su propio note off)\n\n"
            "Los valores actuales se guardan para poder volver a ellos. ¿Activarlo?"),
        "daw_off_confirm": "¿Volver a los ajustes que tenía el Swing antes del modo DAW?",
        "daw_on_done": "Modo DAW activado. En el DAW, activa Sync en la salida MIDI del Swing para que siga su tempo.",
        "daw_off_done": "Ajustes anteriores al modo DAW restaurados.",
        "daw_no_backup": "El Swing ya tiene los ajustes del modo DAW y no hay ajustes anteriores guardados para volver.",
        "bridge": "Puente DAW",
        "bridge_off_hint": "Apagado. Necesita loopMIDI con los puertos «Swing to DAW» y «DAW to Swing».",
        "bridge_on_hint": "Activo: Swing ⇄ loopMIDI ⇄ DAW, con filtros contra bucles y notas pegadas.",
        "bridge_on_done": "Puente DAW activo. En el DAW: entrada «Swing to DAW» (Track) y salida «DAW to Swing» (Sync). Desactiva el puerto «Behringer Swing».",
        "bridge_off_done": "Puente DAW apagado.",
        "bridge_missing": "No se pudo abrir el puente: {err}. Abre loopMIDI y crea los puertos «Swing to DAW» y «DAW to Swing».",
        "panic": "Pánico",
        "panic_done": "Pánico enviado al DAW: notas, sustain y All Notes Off en los 16 canales.",
        "firmware": "Firmware {v}",
        "no_swing": "Conecta tu Behringer Swing por USB.\nSus ajustes aparecerán aquí automáticamente.",
        "reading": "Leyendo los ajustes del Swing…",
        "read_ok": "Ajustes leídos del Swing.",
        "undo_title": "Deshacer cambios",
        "undo_confirm": "¿Volver a los ajustes que tenía el Swing al conectarlo? Se aplicarán al Swing.",
        "undo_done": "Ajustes originales restaurados.",
        "opened": "Abierto: {path}",
        "saved": "Guardado: {path}",
        "error": "Error: {err}",
        "write_error": "No se pudo aplicar al Swing: {err}",
        "verify_error": "El Swing no guardó un ajuste como se envió ({err}). Se volvieron a leer sus valores.",
        "file_types_json": "Preset de Swing Editor",
        "file_types_syx": "Archivo SysEx",
        "midi": "MIDI",
        "keyboard": "Teclado",
        "pedals": "Pedales",
        "mod_pitch": "Mod y pitch",
        "clock": "Reloj y tempo",
        "sequencer": "Secuenciador",
        "transpose": "Transposición",
        "cv": "CV / Gate",
        "transport": "Transporte",
        "lights": "Luces",
    },
    "en": {
        "title": "Swing Editor · Unofficial project",
        "heading": "Swing settings",
        "subheading": "Behringer Swing · Unofficial project",
        "disclaimer": "Unofficial project, not affiliated with Behringer/Music Tribe.",
        "status_searching": "○   Looking for the Swing…",
        "status_busy": "⚠   Swing in use by another program",
        "port_busy": "Another program is using the Swing (a DAW such as Ableton, or Control Tribe). Close it, or turn the Swing off in the DAW's MIDI preferences; the editor will connect by itself.",
        "status_reading": "●   Swing linked · reading settings…",
        "status_linked": "●   Swing linked",
        "status_writing": "●   Swing linked · applying changes…",
        "status_written": "✓   Swing linked · changes applied",
        "status_failed": "⚠   Could not apply · click to retry",
        "open": "Open…",
        "save": "Save…",
        "undo_all": "Undo changes",
        "daw_on": "DAW mode",
        "daw_off": "Leave DAW mode",
        "daw_on_confirm": (
            "DAW mode gets the Swing ready for a DAW over USB:\n\n"
            "• Play, Stop and Rec on channel 16 (kept apart from the notes)\n"
            "• Mod strip on the standard CC 1\n"
            "• MIDI Thru off\n"
            "• Transposition from USB only\n"
            "• Linear velocity\n"
            "• Transport as MIDI CC only (no MMC: a button never acts twice)\n"
            "• Hold keeps the keys (each note ends with its own note off)\n\n"
            "The current values are saved so you can go back to them. Turn it on?"),
        "daw_off_confirm": "Go back to the settings the Swing had before DAW mode?",
        "daw_on_done": "DAW mode on. In your DAW, turn Sync on for the Swing's MIDI output so it follows the tempo.",
        "daw_off_done": "Settings from before DAW mode restored.",
        "daw_no_backup": "The Swing already has the DAW mode settings and there are no earlier settings saved to go back to.",
        "bridge": "DAW bridge",
        "bridge_off_hint": "Off. Needs loopMIDI with the ports “Swing to DAW” and “DAW to Swing”.",
        "bridge_on_hint": "On: Swing ⇄ loopMIDI ⇄ DAW, with filters against loops and stuck notes.",
        "bridge_on_done": "DAW bridge on. In the DAW: input “Swing to DAW” (Track) and output “DAW to Swing” (Sync). Turn off the “Behringer Swing” port.",
        "bridge_off_done": "DAW bridge off.",
        "bridge_missing": "Could not open the bridge: {err}. Open loopMIDI and create the ports “Swing to DAW” and “DAW to Swing”.",
        "panic": "Panic",
        "panic_done": "Panic sent to the DAW: notes, sustain and All Notes Off on all 16 channels.",
        "firmware": "Firmware {v}",
        "no_swing": "Connect your Behringer Swing by USB.\nIts settings will show up here automatically.",
        "reading": "Reading the Swing's settings…",
        "read_ok": "Settings read from the Swing.",
        "undo_title": "Undo changes",
        "undo_confirm": "Go back to the settings the Swing had when it was connected? They will be applied to the Swing.",
        "undo_done": "Original settings restored.",
        "opened": "Opened: {path}",
        "saved": "Saved: {path}",
        "error": "Error: {err}",
        "write_error": "Could not apply to the Swing: {err}",
        "verify_error": "The Swing did not store a setting as sent ({err}). Its values were read again.",
        "file_types_json": "Swing Editor preset",
        "file_types_syx": "SysEx file",
        "midi": "MIDI",
        "keyboard": "Keyboard",
        "pedals": "Pedals",
        "mod_pitch": "Mod & pitch",
        "clock": "Clock & tempo",
        "sequencer": "Sequencer",
        "transpose": "Transposition",
        "cv": "CV / Gate",
        "transport": "Transport",
        "lights": "Lights",
    },
}

# key: (Spanish label, Spanish help, English label, English help)
PARAM_TEXTS = {
    "output_channel": ("Canal de salida", "Canal MIDI en el que el teclado envía las notas.",
                       "Output channel", "MIDI channel the keyboard plays on."),
    "midi_in_channel": ("Canal de entrada", "Canal MIDI que escucha el Swing (User = el canal de salida).",
                        "Input channel", "MIDI channel the Swing listens to (User = the output channel)."),
    "midi_thru": ("MIDI Thru", "Reenvía por MIDI Out lo que entra por MIDI In.",
                  "MIDI Thru", "Sends what arrives at MIDI In back out of MIDI Out."),
    "velocity_curve": ("Curva de velocidad", "Cómo responde el volumen a la fuerza con que tocas.",
                       "Velocity curve", "How note velocity follows how hard you play."),
    "velocity_mode": ("Velocidad", "Según cómo toques, o siempre la misma (velocidad fija).",
                      "Velocity", "As you play it, or always the same (fixed velocity)."),
    "fixed_velocity": ("Velocidad fija", "Valor usado cuando la velocidad es fija.",
                       "Fixed velocity", "Value used when velocity is fixed."),
    "sustain_function": ("Función del pedal", "Qué hace el pedal de sustain.",
                         "Sustain pedal function", "What the sustain pedal does."),
    "sustain_mode": ("Modo del pedal", "Gate: mientras lo pisas. Toggle: pisar activa, volver a pisar desactiva.",
                     "Sustain pedal mode", "Gate: works while pressed. Toggle: press once for on, again for off."),
    "sustain_channel": ("Canal del mensaje de sustain", "Canal del CC de sustain (User = el canal de salida).",
                        "Sustain message channel", "Channel of the sustain CC (User = the output channel)."),
    "sustain_cc": ("CC del pedal", "Número de CC que envía el pedal (64 es el sustain estándar).",
                   "Sustain CC number", "CC number the pedal sends (64 is the standard sustain)."),
    "sustain_cc_low": ("Valor al soltar", "Valor del CC cuando sueltas el pedal.",
                       "Value when released", "CC value when the pedal is released."),
    "sustain_cc_high": ("Valor al pisar", "Valor del CC cuando pisas el pedal.",
                        "Value when pressed", "CC value when the pedal is pressed."),
    "hold_function": ("Función del botón Hold", "Qué hace el botón Hold del panel.",
                      "Hold switch function", "What the Hold button does."),
    "hold_mode": ("Modo del botón Hold", "Gate: mientras lo mantienes. Toggle: pulsar activa, volver a pulsar desactiva.",
                  "Hold switch mode", "Gate: works while held. Toggle: press once for on, again for off."),
    "mod_channel": ("Canal de la tira Mod", "Canal MIDI de la tira de modulación (User = el canal de salida).",
                    "Mod strip channel", "MIDI channel of the modulation strip (User = the output channel)."),
    "mod_cc": ("CC de la tira Mod", "Número de CC que envía la tira de modulación.",
               "Mod strip CC", "CC number the modulation strip sends."),
    "pitch_bend_channel": ("Canal de la tira Pitch", "Canal MIDI del pitch bend (User = el canal de salida).",
                           "Pitch strip channel", "MIDI channel of the pitch bend (User = the output channel)."),
    "clock_mode": ("Entrada de reloj", "Qué tipo de pulso espera la entrada Sync/Clock.",
                   "Clock input", "Kind of pulse the Sync/Clock input expects."),
    "clock_start": ("Arranque con reloj externo", "Cuándo empieza a sonar al recibir reloj externo.",
                    "Start with external clock", "When playback starts with an external clock."),
    "tap_tempo_count": ("Tap tempo", "Cuántos toques se promedian para calcular el tempo.",
                        "Tap tempo", "How many taps are averaged to set the tempo."),
    "next_sequence": ("Siguiente secuencia", "Cuándo cambia a la secuencia elegida mientras suena.",
                      "Next sequence", "When it switches to the chosen sequence while playing."),
    "arm_to_start": ("Armar para empezar", "Espera a que toques una tecla para arrancar.",
                     "Arm to start", "Waits for a key press to start playing."),
    "tie_mode": ("Modo de ligado", "Cómo se liga una nota con la anterior o la siguiente.",
                 "Tie mode", "How a tied note joins the previous or next one."),
    "transpose_port": ("Entrada de transposición", "Por dónde llegan las notas que transponen la secuencia.",
                       "Transposition input", "Where the notes that transpose the sequence come from."),
    "transpose_channel": ("Canal de transposición", "Canal MIDI de esas notas.",
                          "Transposition channel", "MIDI channel of those notes."),
    "transpose_latch": ("Mantener transposición", "La transposición se queda al soltar la tecla.",
                        "Transposition latch", "Transposition stays when the key is released."),
    "transpose_center": ("Nota central", "La nota que no transpone (a partir de ella se sube o baja).",
                         "Center note", "The note that does not transpose (others move up or down from it)."),
    "gate_output": ("Nivel de Gate", "Tipo de señal de la salida Gate.",
                    "Gate output level", "Kind of signal on the Gate output."),
    "pitch_output": ("Modo de Pitch CV", "Estándar de la salida de tono.",
                     "Pitch CV mode", "Standard of the pitch output."),
    "pitch_0v_note": ("Nota a 0 V", "Nota que da 0 voltios en Pitch CV.",
                      "Note at 0 V", "Note that gives 0 volts on Pitch CV."),
    "pitch_1v_note": ("Nota a 1 V", "Nota que da 1 voltio en Pitch CV.",
                      "Note at 1 V", "Note that gives 1 volt on Pitch CV."),
    "note_priority": ("Prioridad de nota", "Qué nota manda el CV si tocas varias a la vez.",
                      "Note priority", "Which note the CV follows when several are held."),
    "pitch_range": ("Rango de pitch", "Rango de la salida de tono.",
                    "Pitch range", "Range of the pitch output."),
    "mod_cv_source": ("Fuente de Mod CV", "Qué controla la salida Mod.",
                      "Mod CV source", "What drives the Mod output."),
    "mod_cv_max": ("Voltaje máximo de Mod", "Voltaje más alto de la salida Mod.",
                   "Mod max voltage", "Highest voltage of the Mod output."),
    "transport_mode": ("Mensajes de transporte", "Qué envían Play, Stop y Rec.",
                       "Transport messages", "What Play, Stop and Rec send."),
    "play_pause": ("Botón Play/Pause", "Qué hace pulsar Play mientras suena.",
                   "Play/Pause button", "What pressing Play while playing does."),
    "play_channel": ("Canal de Play", "", "Play channel", ""),
    "play_cc": ("CC de Play", "", "Play CC", ""),
    "stop_channel": ("Canal de Stop", "", "Stop channel", ""),
    "stop_cc": ("CC de Stop", "", "Stop CC", ""),
    "rec_channel": ("Canal de Rec", "", "Rec channel", ""),
    "rec_cc": ("CC de Rec", "", "Rec CC", ""),
    "led_brightness": ("Brillo de los LEDs", "Intensidad de las luces del panel.",
                       "LED brightness", "How bright the panel lights are."),
    # read only, not shown in the window
    "aftertouch_curve": ("Curva de aftertouch", "", "Aftertouch curve", ""),
    "tempo_knob": ("Perilla de tempo", "", "Tempo knob", ""),
    "arpeggiator_random": ("Aleatorio del arpegiador", "", "Arpeggiator random", ""),
}

OPTION_ES = {
    "Off": "Apagado", "On": "Encendido", "User": "User (canal de salida)", "All": "Todos", "None": "Ninguno",
    "Linear": "Lineal", "Logarithmic": "Logarítmica", "Anti-logarithmic": "Antilogarítmica",
    "As played": "Según toques", "Fixed": "Fija",
    "Hold keys": "Mantener teclas", "Sustain message": "Mensaje de sustain", "Both": "Ambos",
    "Gate": "Gate", "Toggle": "Toggle",
    "1 step (gate)": "1 paso (gate)", "1 step (clock)": "1 paso (clock)", "1 pulse (Korg)": "1 pulso (Korg)",
    "On clock": "Con el reloj", "On gate start": "Con el inicio de gate",
    "2 taps": "2 toques", "3 taps": "3 toques", "4 taps": "4 toques",
    "At the end": "Al terminar", "Instant reset": "Al instante, desde el principio",
    "Instant continue": "Al instante, sin perder el paso",
    "Tie to previous": "Ligar a la anterior", "Tie to next": "Ligar a la siguiente",
    "USB": "USB", "MIDI": "MIDI", "USB and MIDI": "USB y MIDI",
    "S-trig": "S-trig", "V-trig 5 V": "V-trig 5 V", "V-trig 12 V": "V-trig 12 V",
    "Volts per octave": "Voltios por octava", "Hertz per volt": "Hercios por voltio",
    "Low": "Grave", "High": "Aguda", "Last": "Última",
    "Mod strip": "Tira Mod", "Velocity": "Velocidad", "Aftertouch": "Aftertouch",
    "MIDI CC": "MIDI CC", "MMC": "MMC", "Pause": "Pausa", "Reset": "Volver al inicio",
}


def detect_language():
    """'es' when Windows reports a Spanish locale ("es_MX" or "Spanish_Mexico"), else 'en'."""
    try:
        name = locale.getlocale()[0]
    except ValueError:
        name = None
    return "es" if name and name.lower().startswith(("es", "spanish")) else "en"


class Translator:
    def __init__(self, lang=None):
        self.lang = lang if lang in TEXTS else detect_language()

    def __call__(self, key, **kw):
        return TEXTS[self.lang][key].format(**kw)

    def param_label(self, param):
        es_label, _, en_label, _ = PARAM_TEXTS[param.key]
        return es_label if self.lang == "es" else en_label

    def param_help(self, param):
        _, es_help, _, en_help = PARAM_TEXTS[param.key]
        return es_help if self.lang == "es" else en_help

    def option(self, label):
        return OPTION_ES.get(label, label) if self.lang == "es" else label
