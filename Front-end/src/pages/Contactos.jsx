import {
    FiClock,
    FiHelpCircle,
    FiMail,
    FiMap,
    FiMapPin,
    FiMessageCircle,
    FiPhone,
    FiSend,
} from 'react-icons/fi';

import { useEventTheme } from '../context/EventThemeContext';
import styles from '../styles/pages/DynamicPage.module.css';

const contactCards = [
    {
        icon: <FiMapPin />,
        title: 'Ubicación',
        text: 'Bogotá, carrera 13 # 47 - 30',
        detail: 'Universidad Católica de Colombia, Centro de Convenciones, sede 4.',
    },
    {
        icon: <FiMail />,
        title: 'Correo electrónico',
        text: 'coniiti@ucatolica.edu.co',
        detail: 'Canal principal para preguntas generales e inscripciones.',
        link: 'mailto:coniiti@ucatolica.edu.co',
    },
    {
        icon: <FiPhone />,
        title: 'Teléfonos',
        text: 'PBX: (601) 4433700',
        detail: 'Extensiones: 3130 / 3160 / 3190',
    },
];

const quickQuestions = [
    'Inscripciones y registro al congreso.',
    'Agenda, horarios y actividades académicas.',
    'Soporte para participantes, ponentes y autores.',
];

export default function Contactos() {
    const { siteConfig, isModuleVisible } = useEventTheme();
    const contact = siteConfig.pages.contact;
    const configuredCards = [
        { ...contactCards[0], text: contact.address },
        { ...contactCards[1], text: contact.email, link: `mailto:${contact.email}` },
        { ...contactCards[2], text: contact.phone },
    ];
    if (!isModuleVisible('contact')) {
        return <div className={styles.page}><div className={styles.container}><div className={styles.empty}><h1>Contacto no disponible</h1><p>Este módulo está oculto temporalmente.</p></div></div></div>;
    }
    return (
        <div className={styles.page}>
            <section className={`${styles.hero} ${styles.heroSplit}`}>
                <div className={styles.heroContent}>
                    <span className={styles.eyebrow}>Canales oficiales</span>
                    <h1>{contact.title}</h1>
                    <p>{contact.message}</p>
                </div>
                <a className={styles.heroAction} href={`mailto:${contact.email}`}>
                    <FiSend />
                    Enviar correo
                </a>
            </section>

            <div className={styles.container}>
                <section className={styles.contactLayout}>
                    <div className={styles.contactCards}>
                        {configuredCards.map((card) => (
                            <article className={styles.contactCard} key={card.title}>
                                <div className={styles.iconWrapper}>{card.icon}</div>
                                <div>
                                    <h2>{card.title}</h2>
                                    {card.link ? (
                                        <a href={card.link}>{card.text}</a>
                                    ) : (
                                        <p className={styles.contactMain}>{card.text}</p>
                                    )}
                                    <p>{card.detail}</p>
                                </div>
                            </article>
                        ))}
                    </div>

                    <aside className={styles.mapPanel} aria-label="Referencia de ubicación">
                        <div className={styles.mapVisual}>
                            <FiMap />
                            <span>Universidad Católica de Colombia</span>
                            <strong>Centro de Convenciones, sede 4</strong>
                        </div>
                        <div className={styles.mapFooter}>
                            <FiMapPin />
                            <span>{contact.address}</span>
                        </div>
                    </aside>
                </section>

                <section className={styles.infoGrid}>
                    <article className={styles.infoPanel}>
                        <div className={styles.panelTitle}>
                            <FiClock />
                            <h2>Horarios y canal de consulta</h2>
                        </div>
                        <p>
                            Puedes escribir al correo institucional para recibir orientación sobre el
                            proceso de participación. Las respuestas se atienden por los canales oficiales
                            de la universidad y del congreso.
                        </p>
                        <a className={styles.primaryButton} href={`mailto:${contact.email}`}>
                            <FiMail />
                            Enviar correo
                        </a>
                    </article>

                    <article className={styles.infoPanel}>
                        <div className={styles.panelTitle}>
                            <FiHelpCircle />
                            <h2>Preguntas rápidas</h2>
                        </div>
                        <div className={styles.quickList}>
                            {quickQuestions.map((question) => (
                                <div className={styles.quickItem} key={question}>
                                    <FiMessageCircle />
                                    <span>{question}</span>
                                </div>
                            ))}
                        </div>
                    </article>
                </section>
            </div>
        </div>
    );
}
