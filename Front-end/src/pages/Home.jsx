import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
    FiArrowRight,
    FiAward,
    FiBookOpen,
    FiBriefcase,
    FiCheck,
    FiChevronLeft,
    FiChevronRight,
    FiLink,
    FiMonitor,
    FiUsers,
} from 'react-icons/fi';

import SpeakerCard from '../components/SpeakerCard';
import { useAuth } from '../context/AuthContext';
import { useEventTheme } from '../context/EventThemeContext';
import { getApiBase } from '../services/apiConfig';
import { createCheckout, PAYMENT_PLANS } from '../services/paymentService';
import styles from '../styles/pages/Home.module.css';


const API_BASE = getApiBase();
const SPEAKERS_PER_PAGE = 5;

function zonedDateStart(dateValue, timeZone) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateValue ?? '');
    if (!match || !timeZone) return null;
    const [, year, month, day] = match.map(Number);
    const requestedWallTime = Date.UTC(year, month - 1, day);
    let instant = requestedWallTime;
    try {
        const formatter = new Intl.DateTimeFormat('en-CA', {
            timeZone,
            hourCycle: 'h23',
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
        });
        for (let attempt = 0; attempt < 2; attempt += 1) {
            const parts = Object.fromEntries(
                formatter.formatToParts(new Date(instant))
                    .filter((part) => part.type !== 'literal')
                    .map((part) => [part.type, Number(part.value)]),
            );
            const observedWallTime = Date.UTC(
                parts.year, parts.month - 1, parts.day,
                parts.hour, parts.minute, parts.second,
            );
            instant += requestedWallTime - observedWallTime;
        }
        return instant;
    } catch {
        return null;
    }
}

function calculateTimeLeft(now, target) {
    const difference = target - now;

    if (difference <= 0) return {};

    return {
        days: Math.floor(difference / (1000 * 60 * 60 * 24)),
        hours: Math.floor((difference / (1000 * 60 * 60)) % 24),
        minutes: Math.floor((difference / 1000 / 60) % 60),
        seconds: Math.floor((difference / 1000) % 60),
    };
}


function Countdown({ conferenceDay, timeZone, loading }) {
    const [timeLeft, setTimeLeft] = useState(null);
    const target = zonedDateStart(conferenceDay, timeZone);

    useEffect(() => {
        if (target === null) return undefined;
        const updateTimeLeft = () => setTimeLeft(calculateTimeLeft(Date.now(), target));
        const initialTimer = setTimeout(updateTimeLeft, 0);
        const intervalId = setInterval(updateTimeLeft, 1000);

        return () => {
            clearTimeout(initialTimer);
            clearInterval(intervalId);
        };
    }, [target]);

    if (loading) {
        return <div className={styles.countdownContainer}><h2>Cargando calendario...</h2></div>;
    }

    if (target === null) {
        return <div className={styles.countdownContainer}><h2>Fechas por confirmar.</h2></div>;
    }

    if (timeLeft === null) {
        return <div className={styles.countdownContainer}><h2>Cargando contador...</h2></div>;
    }

    if (!timeLeft.days && timeLeft.days !== 0) {
        return <div className={styles.countdownContainer}><h2>El Congreso ha comenzado.</h2></div>;
    }

    return (
        <div className={styles.countdownContainer}>
            {[
                ['Días', timeLeft.days],
                ['Horas', timeLeft.hours],
                ['Min', timeLeft.minutes],
                ['Seg', timeLeft.seconds],
            ].map(([label, value]) => (
                <div key={label} className={styles.countdownBox}>
                    <span className={styles.countdownValue}>{value}</span>
                    <span className={styles.countdownLabel}>{label}</span>
                </div>
            ))}
        </div>
    );
}


function SpeakerSlider({ speakers }) {
    const [idx, setIdx] = useState(0);
    const timerRef = useRef(null);
    const totalPages = Math.ceil(speakers.length / SPEAKERS_PER_PAGE);

    const next = () => setIdx((current) => (current + 1) % totalPages);
    const prev = () => setIdx((current) => (current - 1 + totalPages) % totalPages);

    useEffect(() => {
        if (totalPages <= 1) return undefined;
        timerRef.current = setInterval(next, 4500);
        return () => clearInterval(timerRef.current);
    });

    if (!speakers.length) return null;

    const visible = speakers.slice(idx * SPEAKERS_PER_PAGE, idx * SPEAKERS_PER_PAGE + SPEAKERS_PER_PAGE);

    return (
        <div style={{ position: 'relative' }}>
            <div className={styles.speakersGrid}>
                {visible.map((speaker, index) => (
                    <SpeakerCard key={speaker.ponente + index} speaker={speaker} />
                ))}
            </div>
            {totalPages > 1 && (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1rem', marginTop: '1.5rem' }}>
                    <button onClick={prev} style={navBtnStyle}><FiChevronLeft size={20} /></button>
                    <span style={{ color: '#64748b', fontSize: '0.85rem' }}>{idx + 1} / {totalPages}</span>
                    <button onClick={next} style={navBtnStyle}><FiChevronRight size={20} /></button>
                </div>
            )}
        </div>
    );
}


const navBtnStyle = {
    background: 'white',
    border: '1px solid #e2e8f0',
    borderRadius: '50%',
    width: '36px',
    height: '36px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    boxShadow: '0 2px 6px rgba(0,0,0,0.08)',
};


function getUserHubPath(user) {
    if (!user) return '/register';
    if (user.role === 'superuser') return '/superusuario';
    if (user.role === 'staff') return '/staff';
    return '/mis-conferencias';
}


function getUserHubLabel(user) {
    if (!user) return 'Crear cuenta';
    if (user.role === 'superuser') return 'Ir al centro de control';
    if (user.role === 'staff') return 'Ir al centro de gestión';
    return 'Ir a mis conferencias';
}


function getAccessHighlights(user) {
    if (!user) {
        return [
            'Crea tu cuenta en pocos pasos',
            'Consulta la agenda y las actividades del congreso',
            'Recibe novedades importantes sobre tu participación',
        ];
    }

    if (user.role === 'superuser') {
        return [
            'Acceso al centro de supervisión del congreso',
            'Vista general de la programación y del equipo',
            'Seguimiento de la actividad y los recursos del evento',
        ];
    }

    if (user.role === 'staff') {
        return [
            'Acceso directo al centro operativo',
            'Gestión de sesiones, contenido y archivos',
            'Seguimiento de cambios y tareas del evento',
        ];
    }

    return [
        'Tu cuenta está lista para continuar',
        'Consulta la agenda y tus actividades',
        'Gestiona tu participación desde un solo lugar',
    ];
}


export default function Home() {
    const { user, isLoading } = useAuth();
    const { agendaConfig, agendaConfigLoading, theme, siteConfig, isModuleVisible } = useEventTheme();
    const [keynotes, setKeynotes] = useState([]);
    const [keynotesLoading, setKeynotesLoading] = useState(true);
    const [keynotesError, setKeynotesError] = useState('');
    const [checkoutLoadingKey, setCheckoutLoadingKey] = useState('');
    const [checkoutError, setCheckoutError] = useState('');

    useEffect(() => {
        let active = true;
        fetch(`${API_BASE}/agenda/speakers?principal_only=true`)
            .then((response) => {
                if (!response.ok) throw new Error('No se pudieron consultar los conferencistas.');
                return response.json();
            })
            .then((data) => {
                if (!active) return;
                setKeynotes(Array.isArray(data) ? data : []);
                setKeynotesError('');
            })
            .catch((requestError) => {
                if (!active) return;
                setKeynotes([]);
                setKeynotesError(requestError.message);
            })
            .finally(() => { if (active) setKeynotesLoading(false); });
        return () => { active = false; };
    }, []);

    const handleCheckout = async (plan, region) => {
        if (!user) return;

        const loadingKey = `${plan.id}-${region}`;
        setCheckoutLoadingKey(loadingKey);
        setCheckoutError('');

        try {
            const isLocal = region === 'LOCAL';
            const payment = await createCheckout({
                userId: user.id,
                amount: isLocal ? plan.localAmount : plan.internationalAmount,
                currency: isLocal ? plan.localCurrency : plan.internationalCurrency,
                paymentRegion: region,
            });

            if (!payment?.checkout_url) {
                throw new Error('No fue posible iniciar el pago. Inténtalo de nuevo.');
            }

            window.location.assign(payment.checkout_url);
        } catch (error) {
            setCheckoutError(error.message);
        } finally {
            setCheckoutLoadingKey('');
        }
    };

    return (
        <div className={styles.home}>
            <header className={styles.hero}>
                <div className={styles.heroBackground}>
                    <img src={siteConfig.branding.hero_url || "/colosseum_italy_hero.png"} alt={siteConfig.event.title} fetchPriority="high" width="1920" height="1080" />
                </div>
                <div className={styles.heroOverlay}></div>
                {theme.siteAccentsEnabled && <div className={styles.guestRibbon} aria-hidden="true" />}

                <div className={styles.heroContent}>
                    {theme.editionLabel && <span className={styles.badge}>{theme.editionLabel}</span>}
                    <h1>{siteConfig.pages.home.title}</h1>
                    <p>
                        {user
                            ? `Bienvenido${user.full_name ? `, ${user.full_name}` : ''}. Tu sesión ya está activa para participar en CONIITI 2026.`
                            : siteConfig.pages.home.subtitle}
                    </p>

                    <Countdown
                        conferenceDay={agendaConfig?.conference_days?.[0]}
                        timeZone={agendaConfig?.timezone}
                        loading={agendaConfigLoading}
                    />

                    <div className={styles.heroButtons}>
                        {isModuleVisible('agenda') && <Link to="/agenda" className={styles.primaryBtn}>
                            {siteConfig.pages.home.cta_label} <FiArrowRight />
                        </Link>}
                        {!isLoading && (
                            <Link to={getUserHubPath(user)} className={styles.secondaryBtn}>
                                {getUserHubLabel(user)}
                            </Link>
                        )}
                    </div>
                </div>
            </header>

            <section className={`${styles.sectionBlock} ${styles.whySection}`}>
                <div className={styles.whyHeader}>
                    <span className={styles.preTitle}>Por qué asistir al</span>
                    <h2 className={styles.mainTitleBlue}>XI Congreso Internacional de Innovación y Tendencias en Ingeniería</h2>
                </div>

                <div className={styles.whyGridCenter}>
                    <div className={styles.whyColLeft}>
                        <div className={styles.whyFeatureCard}>
                            <div className={styles.featureIcon}><FiUsers /></div>
                            <h3>Networking de alto nivel</h3>
                            <p>Conecta con líderes de la industria, investigadores y equipos con los que podrás construir alianzas reales.</p>
                        </div>
                        <div className={styles.whyFeatureCard}>
                            <div className={styles.featureIcon}><FiLink /></div>
                            <h3>Alianzas estratégicas</h3>
                            <p>Las sesiones del congreso están pensadas para crear proyectos conjuntos de impacto académico y profesional.</p>
                        </div>
                    </div>

                    <div className={styles.whyColCenter}>
                        <div className={styles.centerGraphicPulse}>
                            <div className={styles.coreOrb}></div>
                            <div className={`${styles.orbit} ${styles.orb1}`}></div>
                            <div className={`${styles.orbit} ${styles.orb2}`}></div>
                            <div className={`${styles.orbit} ${styles.orb3}`}></div>
                        </div>
                    </div>

                    <div className={styles.whyColRight}>
                        <div className={styles.whyFeatureCard}>
                            <div className={styles.featureIcon}><FiBriefcase /></div>
                            <h3>Conferencias y talleres</h3>
                            <p>Accede a plenarias y talleres centrados en software, datos, IA, ciberseguridad y transformación digital.</p>
                        </div>
                        <div className={styles.whyFeatureCard}>
                            <div className={styles.featureIcon}><FiMonitor /></div>
                            <h3>Desarrollo profesional</h3>
                            <p>Fortalece tu perfil técnico con contenido vigente y experiencias de aplicación real.</p>
                        </div>
                    </div>
                </div>
            </section>

            <section className={`${styles.sectionBlock} ${styles.darkBg} ${styles.fullWidthBlock}`}>
                <div className={styles.darkBgInner}>
                    <h2 className={styles.sectionTitle}>Impacto CONIITI</h2>
                    <p className={styles.sectionSubtitle}>Una plataforma que integra academia, industria y comunidad tecnológica.</p>

                    <div className={styles.impactGrid}>
                        <div className={styles.impactCard}>
                            <div className={styles.impactIcon}><FiUsers /></div>
                            <div className={styles.impactNumber}>95+</div>
                            <div className={styles.impactLabel}>Conferencistas Principales</div>
                        </div>
                        <div className={styles.impactCard}>
                            <div className={styles.impactIcon}><FiAward /></div>
                            <div className={styles.impactNumber}>12</div>
                            <div className={styles.impactLabel}>Países invitados</div>
                        </div>
                        <div className={styles.impactCard}>
                            <div className={styles.impactIcon}><FiBookOpen /></div>
                            <div className={styles.impactNumber}>30+</div>
                            <div className={styles.impactLabel}>Workshops y ponencias</div>
                        </div>
                        <div className={styles.impactCard}>
                            <div className={styles.impactIcon}><FiUsers /></div>
                            <div className={styles.impactNumber}>999+</div>
                            <div className={styles.impactLabel}>Participantes esperados</div>
                        </div>
                    </div>
                </div>
            </section>

            {isModuleVisible('speakers') && <section className={styles.sectionBlock}>
                <h2 className={styles.sectionTitle}>Conferencistas Principales</h2>
                <p className={styles.sectionSubtitle}>Conoce a algunos de los expertos que guiarán las plenarias de innovación.</p>

                {keynotesLoading ? (
                    <p className={styles.sectionSubtitle}>Consultando conferencistas oficiales…</p>
                ) : keynotesError ? (
                    <p className={styles.sectionSubtitle} role="status">Información no disponible en este momento. {keynotesError}</p>
                ) : keynotes.length > 0 ? (
                    <SpeakerSlider speakers={keynotes} />
                ) : (
                    <p className={styles.sectionSubtitle}>Aún no hay conferencistas principales publicados.</p>
                )}

                <div className={styles.centerBtn}>
                    <Link to="/conferencistas" className={styles.primaryBtn}>Conoce a todos los conferencistas</Link>
                </div>
            </section>}

            {isModuleVisible('payments') && <section id="inscripciones" className={`${styles.sectionBlock} ${styles.blueBg}`}>
                {user ? (
                    <div className={styles.accessContainer}>
                        <h2 className={styles.sectionTitle}>Opciones de pago</h2>
                        <p className={styles.sectionSubtitle}>
                            Tu sesión está activa. Elige la opción de pago que prefieras para completar tu inscripción.
                        </p>

                        {!!checkoutError && (
                            <p className={styles.paymentError}>{checkoutError}</p>
                        )}

                        <div className={styles.pricingGrid}>
                            {PAYMENT_PLANS.map((plan) => (
                                <article
                                    key={plan.id}
                                    className={`${styles.pricingCard} ${plan.optional ? styles.optionalCard : ''}`}
                                >
                                    {plan.optional && <span className={styles.optionalBadge}>Opcional</span>}
                                    <h3 className={styles.pricingTitle}>{plan.title}</h3>
                                    <div className={styles.pricingAmount}>
                                        {plan.amountLabel}
                                        <span> COP</span>
                                    </div>
                                    <div className={styles.paymentProviders}>
                                        <span>Mercado Pago</span>
                                        <span>PayPal</span>
                                    </div>
                                    <ul className={styles.pricingFeatures}>
                                        {plan.features.map((feature) => (
                                            <li key={feature}><FiCheck size={20} color="#ffc107" /> {feature}</li>
                                        ))}
                                    </ul>
                                    <div className={styles.paymentActions}>
                                        <button
                                            type="button"
                                            className={styles.pricingBtn}
                                            onClick={() => handleCheckout(plan, 'LOCAL')}
                                            disabled={checkoutLoadingKey !== ''}
                                        >
                                            {checkoutLoadingKey === `${plan.id}-LOCAL` ? 'Conectando...' : 'Pagar en Colombia'}
                                        </button>
                                        <button
                                            type="button"
                                            className={`${styles.pricingBtn} ${styles.paymentAltBtn}`}
                                            onClick={() => handleCheckout(plan, 'INTERNATIONAL')}
                                            disabled={checkoutLoadingKey !== ''}
                                        >
                                            {checkoutLoadingKey === `${plan.id}-INTERNATIONAL` ? 'Conectando...' : 'Pagar internacional'}
                                        </button>
                                    </div>
                                </article>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className={styles.pricingContainer}>
                        <h2 className={styles.sectionTitle}>Inscripciones</h2>
                        <p className={styles.sectionSubtitle}>
                            Crea tu cuenta para registrarte, consultar la agenda y continuar tu proceso de participación.
                        </p>

                        <div className={styles.pricingGrid}>
                            <div className={styles.pricingCard}>
                                <h3 className={styles.pricingTitle}>Ponentes y asistentes</h3>
                                <div className={styles.pricingAmount}>Registro digital</div>
                                <ul className={styles.pricingFeatures}>
                                    {getAccessHighlights(null).map((item) => (
                                        <li key={item}><FiCheck size={20} color="#ffc107" /> {item}</li>
                                    ))}
                                </ul>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                                    <Link className={styles.pricingBtn} to="/register">Crear cuenta e inscribirme</Link>
                                    <Link className={styles.pricingBtn} style={{ background: '#0070ba' }} to="/login">Ya tengo cuenta</Link>
                                </div>
                            </div>

                            <div className={styles.pricingCard}>
                                <h3 className={styles.pricingTitle}>Soporte de inscripción</h3>
                                <div className={styles.pricingAmount}>Canal oficial</div>
                                <ul className={styles.pricingFeatures}>
                                    <li><FiCheck size={20} color="#ffc107" /> Atención para participantes internacionales</li>
                                    <li><FiCheck size={20} color="#ffc107" /> Gestión de certificados y consultas</li>
                                    <li><FiCheck size={20} color="#ffc107" /> Acompañamiento del equipo CONIITI</li>
                                </ul>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                                    <a className={styles.pricingBtn} href="mailto:coniiti@ucatolica.edu.co">Escribir a soporte</a>
                                    <Link className={styles.pricingBtn} style={{ background: '#0070ba' }} to="/agenda">Explorar agenda</Link>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </section>}
        </div>
    );
}
