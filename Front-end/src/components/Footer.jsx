import styles from '../styles/components/Footer.module.css';
import { useEventTheme } from '../context/EventThemeContext';

export default function Footer() {
    const { siteConfig } = useEventTheme();
    const event = siteConfig.event;
    return (
        <footer className={styles.footer}>
            <div className={styles.inner}>
                <span className={styles.brand}>
                    <span className={styles.accent}>C</span>oniiti
                </span>
                <hr className={styles.divider} />
                <p className={styles.info}>
                    {event.title} — {event.subtitle}
                    <br />
                    {event.location_label}
                </p>
                <p className={styles.copy}>
                    © 2026 CONIITI | Universidad Católica de Colombia
                </p>
            </div>
        </footer>
    );
}
