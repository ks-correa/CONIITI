import { useCallback, useEffect, useState } from 'react';
import QRCode from 'react-qr-code';
import { FiCheckCircle, FiClipboard, FiRefreshCw, FiSlash, FiUserCheck } from 'react-icons/fi';

import {
    confirmManualAttendance, getSessionAttendance, getSessions,
    issueAttendanceToken, revokeAttendance,
} from '../../services/agendaService';
import styles from '../../styles/components/AttendanceManager.module.css';


export default function AttendanceManager({ initialSessions }) {
    const [sessions, setSessions] = useState(initialSessions ?? []);
    const [sessionId, setSessionId] = useState(initialSessions?.[0]?.id ?? '');
    const [attendance, setAttendance] = useState([]);
    const [issuedToken, setIssuedToken] = useState(null);
    const [ttlSeconds, setTtlSeconds] = useState(120);
    const [maxUses, setMaxUses] = useState(1);
    const [manualUserId, setManualUserId] = useState('');
    const [manualReason, setManualReason] = useState('Verificación presencial por staff');
    const [error, setError] = useState('');

    useEffect(() => {
        if (!initialSessions) getSessions().then((items) => {
            setSessions(items);
            setSessionId((current) => current || items[0]?.id || '');
        }).catch((requestError) => setError(requestError.message));
    }, [initialSessions]);

    const refresh = useCallback(async () => {
        if (!sessionId) return;
        try {
            setAttendance(await getSessionAttendance(sessionId, { includeRevoked: true }));
            setError('');
        } catch (requestError) { setError(requestError.message); }
    }, [sessionId]);

    useEffect(() => {
        const timer = window.setTimeout(refresh, 0);
        return () => window.clearTimeout(timer);
    }, [refresh]);

    const generate = async () => {
        try {
            setIssuedToken(await issueAttendanceToken(sessionId, {
                ttl_seconds: Number(ttlSeconds), max_uses: Number(maxUses),
            }));
            setError('');
        } catch (requestError) { setError(requestError.message); }
    };

    const manual = async (event) => {
        event.preventDefault();
        try {
            await confirmManualAttendance(sessionId, manualUserId, manualReason);
            setManualUserId('');
            await refresh();
        } catch (requestError) { setError(requestError.message); }
    };

    const revoke = async (item) => {
        const reason = window.prompt('Motivo de revocación (queda auditado):');
        if (!reason) return;
        try { await revokeAttendance(sessionId, item.id, reason); await refresh(); }
        catch (requestError) { setError(requestError.message); }
    };

    return (
        <section className={styles.manager} aria-labelledby="attendance-manager-title">
            <header><div><FiUserCheck /><div><h2 id="attendance-manager-title">Control de asistencia</h2><p>Tokens firmados, cortos y con usos limitados.</p></div></div><button type="button" onClick={refresh}><FiRefreshCw /> Actualizar</button></header>
            {error && <p className={styles.error} role="alert">{error}</p>}
            <label className={styles.sessionSelect}>Sesión<select value={sessionId} onChange={(event) => { setSessionId(event.target.value); setIssuedToken(null); }}>{sessions.map((session) => <option key={session.id} value={session.id}>{session.titulo}</option>)}</select></label>

            <div className={styles.columns}>
                <div className={styles.card}>
                    <h3>QR temporal</h3>
                    <div className={styles.options}>
                        <label>Vigencia (seg.)<input type="number" min="30" max="600" value={ttlSeconds} onChange={(event) => setTtlSeconds(event.target.value)} /></label>
                        <label>Usos máximos<input type="number" min="1" max="5000" value={maxUses} onChange={(event) => setMaxUses(event.target.value)} /></label>
                    </div>
                    <button type="button" onClick={generate} disabled={!sessionId}>Generar token firmado</button>
                    {issuedToken && (
                        <div className={styles.qr}>
                            <QRCode value={issuedToken.token} size={220} level="M" title="QR temporal de asistencia" />
                            <small>Vence: {new Date(issuedToken.expires_at).toLocaleString('es-CO')}</small>
                            <button type="button" onClick={() => navigator.clipboard.writeText(issuedToken.token)}><FiClipboard /> Copiar token</button>
                        </div>
                    )}
                </div>

                <form className={styles.card} onSubmit={manual}>
                    <h3>Alternativa manual accesible</h3>
                    <label>UUID del usuario<input value={manualUserId} onChange={(event) => setManualUserId(event.target.value)} required pattern="[0-9a-fA-F-]{36}" /></label>
                    <label>Motivo<textarea value={manualReason} onChange={(event) => setManualReason(event.target.value)} required minLength="3" /></label>
                    <button type="submit" disabled={!sessionId}><FiCheckCircle /> Confirmar manualmente</button>
                </form>
            </div>

            <div className={styles.tableCard}>
                <h3>Evidencias ({attendance.length})</h3>
                <div className={styles.tableWrap}><table><thead><tr><th>Usuario</th><th>Confirmación</th><th>Método</th><th>Estado</th><th>Acción</th></tr></thead><tbody>
                    {attendance.map((item) => <tr key={item.id}><td><code>{item.user_id}</code></td><td>{new Date(item.confirmed_at).toLocaleString('es-CO')}</td><td>{item.method}</td><td>{item.revoked_at ? `Revocada: ${item.revocation_reason}` : 'Vigente'}</td><td>{!item.revoked_at && <button type="button" onClick={() => revoke(item)}><FiSlash /> Revocar</button>}</td></tr>)}
                </tbody></table></div>
            </div>
        </section>
    );
}
