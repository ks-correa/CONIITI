import {
    FiAward,
    FiCalendar,
    FiCompass,
    FiGlobe,
    FiMapPin,
    FiTarget,
    FiTrendingUp,
    FiUsers,
    FiZap,
} from 'react-icons/fi';

import { useEventTheme } from '../context/EventThemeContext';
import styles from '../styles/pages/DynamicPage.module.css';

const pillars = [
    {
        icon: <FiTarget />,
        title: 'Misión académica',
        text: 'Impulsar espacios de intercambio para compartir herramientas, experiencias y conocimientos sobre innovación y tendencias en ingeniería.',
    },
    {
        icon: <FiCompass />,
        title: 'Visión de futuro',
        text: 'Conectar ideas, metodologías y soluciones que aporten a la transformación creativa desde una mirada técnica y humanista.',
    },
    {
        icon: <FiZap />,
        title: 'Innovación aplicada',
        text: 'Promover conversaciones sobre nuevas aproximaciones para diseñar soluciones con visión de ingeniería.',
    },
    {
        icon: <FiUsers />,
        title: 'Comunidad académica',
        text: 'Reunir estudiantes, docentes, investigadores, profesionales y aliados del ecosistema innovador.',
    },
    {
        icon: <FiTrendingUp />,
        title: 'Impacto',
        text: 'Fortalecer redes de aprendizaje y colaboración alrededor de las ingenierías de sistemas, software, telecomunicaciones e informática.',
    },
    {
        icon: <FiGlobe />,
        title: 'Alcance internacional',
        text: 'Integrar miradas académicas de distintos contextos para enriquecer la conversación sobre los retos actuales de la ingeniería.',
    },
    {
        icon: <FiAward />,
        title: 'Calidad académica',
        text: 'Favorecer espacios de divulgación, análisis y reflexión con contenidos pertinentes para la formación y el ejercicio profesional.',
    },
    {
        icon: <FiCalendar />,
        title: 'Encuentro presencial',
        text: 'Concentrar actividades, diálogos y experiencias durante la agenda del congreso para facilitar participación y conexión entre asistentes.',
    },
];

const benefits = [
    'Acceder a perspectivas actuales sobre innovación, tecnología e ingeniería.',
    'Conectar con redes académicas y profesionales de Colombia y otros países.',
    'Compartir experiencias, proyectos y aprendizajes en un entorno colaborativo.',
    'Explorar tendencias que fortalecen la formación y la práctica profesional.',
];

function formatConferenceDays(conferenceDays) {
    if (!conferenceDays?.length) return 'Por confirmar';
    const asDate = (value) => {
        const [year, month, day] = value.split('-').map(Number);
        return new Date(Date.UTC(year, month - 1, day, 12));
    };
    const first = asDate(conferenceDays[0]);
    const last = asDate(conferenceDays[conferenceDays.length - 1]);
    const short = new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', timeZone: 'UTC' });
    const full = new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
    return conferenceDays.length === 1 ? full.format(first) : `${short.format(first)} – ${full.format(last)}`;
}

export default function Acerca() {
    const { agendaConfig, siteConfig, theme, isModuleVisible } = useEventTheme();
    const conferenceDates = formatConferenceDays(agendaConfig?.conference_days);
    const highlights = [
        { icon: <FiAward />, value: agendaConfig?.edition_label ?? 'Por confirmar', label: 'edición oficial' },
        { icon: <FiMapPin />, value: siteConfig.event.location_label, label: 'sede del evento' },
        { icon: <FiCalendar />, value: conferenceDates, label: 'fechas oficiales' },
        { icon: <FiGlobe />, value: theme.country, label: 'país invitado' },
    ];
    if (!isModuleVisible('about')) {
        return <div className={styles.page}><div className={styles.container}><div className={styles.empty}><h1>Sección no disponible</h1><p>La organización ha ocultado temporalmente este contenido.</p></div></div></div>;
    }
    return (
        <div className={styles.page}>
            <section className={`${styles.hero} ${styles.heroSplit}`}>
                <div className={styles.heroContent}>
                    <span className={styles.eyebrow}>Congreso internacional</span>
                    <h1>{siteConfig.pages.about.title}</h1>
                    <p>{siteConfig.pages.about.description}</p>
                </div>
                <div className={styles.heroPanel} aria-label="Datos principales del congreso">
                    <span>{theme.country} · país invitado</span>
                    <strong>{agendaConfig?.edition_label ?? 'Edición por confirmar'}</strong>
                    <small>{conferenceDates} · {siteConfig.event.location_label}</small>
                </div>
            </section>

            <div className={styles.container}>
                <section className={styles.introBand}>
                    <div>
                        <span className={styles.sectionLabel}>Qué es CONIITI</span>
                        <h2>Un espacio para construir conocimiento con alcance global</h2>
                    </div>
                    <p>
                        CONIITI es un espacio abierto de interacción entre actores del ecosistema
                        innovador, orientado a compartir nuevas aproximaciones para la transformación
                        creativa de Colombia a través del diseño de soluciones con visión de ingeniería.
                        Cuenta con participación activa de ponentes internacionales y redes académicas de
                        América y Europa.
                    </p>
                </section>

                <section className={styles.statsGrid} aria-label="Datos destacados">
                    {highlights.map((item) => (
                        <article className={styles.statCard} key={item.label}>
                            <div className={styles.statIcon}>{item.icon}</div>
                            <strong>{item.value}</strong>
                            <span>{item.label}</span>
                        </article>
                    ))}
                </section>

                <section className={styles.sectionBlock}>
                    <div className={styles.sectionHeading}>
                        <span className={styles.sectionLabel}>Propósito y comunidad</span>
                        <h2>Una agenda pensada para aprender, conectar y proyectar</h2>
                    </div>

                    <div className={styles.aboutGrid}>
                        {pillars.map((pillar) => (
                            <article className={styles.featureCard} key={pillar.title}>
                                <div className={styles.iconWrapper}>{pillar.icon}</div>
                                <h3>{pillar.title}</h3>
                                <p>{pillar.text}</p>
                            </article>
                        ))}
                    </div>
                </section>

                <section className={styles.whySection}>
                    <div className={styles.whyContent}>
                        <span className={styles.sectionLabel}>Por qué participar</span>
                        <h2>Beneficios para una comunidad que mira hacia adelante</h2>
                        <p>
                            El congreso facilita el diálogo entre academia, industria y sociedad para
                            comprender mejor los retos actuales de la ingeniería y las oportunidades de
                            innovación.
                        </p>
                    </div>
                    <div className={styles.benefitList}>
                        {benefits.map((benefit) => (
                            <div className={styles.benefitItem} key={benefit}>
                                <FiZap />
                                <span>{benefit}</span>
                            </div>
                        ))}
                    </div>
                </section>
            </div>
        </div>
    );
}
