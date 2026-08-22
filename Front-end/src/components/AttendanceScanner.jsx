import { useEffect, useRef, useState } from 'react';
import { FiCamera, FiCheckCircle, FiType, FiX } from 'react-icons/fi';

import { confirmAttendance } from '../services/agendaService';
import styles from '../styles/components/AttendanceScanner.module.css';


function extractToken(rawValue) {
    const value = rawValue.trim();
    if (!value) return '';
    try {
        const url = new URL(value);
        return url.searchParams.get('attendance_token') || url.searchParams.get('token') || value;
    } catch {
        return value;
    }
}


export default function AttendanceScanner({ session, onClose, onConfirmed }) {
    const videoRef = useRef(null);
    const streamRef = useRef(null);
    const frameRef = useRef(null);
    const [token, setToken] = useState('');
    const [cameraActive, setCameraActive] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');
    const [confirmed, setConfirmed] = useState(null);

    const stopCamera = () => {
        if (frameRef.current) cancelAnimationFrame(frameRef.current);
        streamRef.current?.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        setCameraActive(false);
    };

    useEffect(() => stopCamera, []);

    const submitToken = async (rawToken = token) => {
        const normalized = extractToken(rawToken);
        if (!normalized || isSubmitting) return;
        setIsSubmitting(true);
        setError('');
        try {
            const attendance = await confirmAttendance(session.id, normalized);
            setConfirmed(attendance);
            stopCamera();
            onConfirmed?.(attendance);
        } catch (submitError) {
            setError(submitError.message);
        } finally {
            setIsSubmitting(false);
        }
    };

    const startCamera = async () => {
        setError('');
        if (!('BarcodeDetector' in window)) {
            setError('Este navegador no permite leer QR con la cámara. Puedes pegar o escanear el código en el campo.');
            return;
        }
        try {
            const formats = await window.BarcodeDetector.getSupportedFormats();
            if (!formats.includes('qr_code')) throw new Error('QR no soportado');
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: 'environment' } }, audio: false,
            });
            streamRef.current = stream;
            videoRef.current.srcObject = stream;
            await videoRef.current.play();
            setCameraActive(true);
            const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
            const scan = async () => {
                if (!streamRef.current || !videoRef.current) return;
                try {
                    const results = await detector.detect(videoRef.current);
                    if (results[0]?.rawValue) {
                        setToken(extractToken(results[0].rawValue));
                        await submitToken(results[0].rawValue);
                        return;
                    }
                } catch {
                    // Un frame sin imagen legible es normal; el ciclo continúa.
                }
                frameRef.current = requestAnimationFrame(scan);
            };
            frameRef.current = requestAnimationFrame(scan);
        } catch (cameraError) {
            stopCamera();
            setError(cameraError.name === 'NotAllowedError'
                ? 'No se concedió permiso para usar la cámara.'
                : 'No fue posible iniciar el lector QR. Usa la entrada manual.');
        }
    };

    return (
        <div className={styles.overlay} onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
            <section className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="attendance-title">
                <header>
                    <div>
                        <span>Asistencia verificable</span>
                        <h2 id="attendance-title">{session.titulo}</h2>
                    </div>
                    <button type="button" onClick={onClose} aria-label="Cerrar validación"><FiX /></button>
                </header>

                {confirmed ? (
                    <div className={styles.success} role="status">
                        <FiCheckCircle />
                        <h3>Asistencia confirmada</h3>
                        <p>La verificación quedó guardada en Agenda.</p>
                        <button type="button" onClick={onClose}>Cerrar</button>
                    </div>
                ) : (
                    <div className={styles.body}>
                        <p>Escanea el QR temporal entregado por el equipo del evento. El código vence y no sustituye tu preinscripción.</p>
                        <video ref={videoRef} className={`${styles.camera} ${cameraActive ? styles.cameraVisible : ''}`} muted playsInline aria-label="Vista de la cámara para leer QR" />
                        <button type="button" className={styles.cameraButton} onClick={cameraActive ? stopCamera : startCamera}>
                            <FiCamera /> {cameraActive ? 'Detener cámara' : 'Leer QR con cámara'}
                        </button>
                        <div className={styles.divider}><span>o usa un lector / entrada manual</span></div>
                        <form onSubmit={(event) => { event.preventDefault(); submitToken(); }}>
                            <label htmlFor="attendance-token"><FiType /> Código temporal</label>
                            <textarea id="attendance-token" value={token} onChange={(event) => setToken(event.target.value)} required autoComplete="off" />
                            <button type="submit" disabled={isSubmitting || !token.trim()}>
                                {isSubmitting ? 'Verificando...' : 'Confirmar asistencia'}
                            </button>
                        </form>
                        {error && <p className={styles.error} role="alert">{error}</p>}
                    </div>
                )}
            </section>
        </div>
    );
}
