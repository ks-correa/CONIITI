import { useState, useRef, useEffect, useContext } from 'react';
import { FiSearch, FiMenu, FiX, FiChevronDown, FiBookmark } from 'react-icons/fi';
import { Link, useNavigate, useLocation } from 'react-router-dom';

import logo from '../assets/coniiti_logo.png';
import styles from '../styles/components/Navbar.module.css';
import { AuthContext } from '../context/AuthContext';
import { useEventTheme } from '../context/EventThemeContext';

const LINKS = [
    { name: 'Inicio', path: '/' },
    {
        name: 'Agenda',
        module: 'agenda',
        path: '/agenda',
        dropdown: [
            { name: 'Agenda', path: '/agenda', module: 'agenda' },
            { name: 'Mis conferencias', path: '/mis-conferencias', icon: 'FiBookmark', module: 'agenda' },
        ],
    },
    {
        name: 'Páginas',
        path: '#',
        dropdown: [
            { name: 'Comité', path: '/comite', module: 'committee' },
            { name: 'Conferencistas', path: '/conferencistas', module: 'speakers' },
            { name: 'Autores', path: '/autores', module: 'authors' },
            { name: 'Galería', path: '/galerias', module: 'gallery' },
        ],
    },
    { name: 'Memorias', path: '/memorias', module: 'memories' },
    { name: 'Acerca de', path: '/acerca-de', module: 'about' },
    { name: 'Contacto', path: '/contacto', module: 'contact' },
    { name: 'Estado', path: '/estado' },
];

export default function Navbar({ registeredCount = 0 }) {
    const { user, logout } = useContext(AuthContext);
    const { theme, siteConfig, isModuleVisible } = useEventTheme();
    const navigate = useNavigate();
    const location = useLocation();
    const activePage = location.pathname;

    const [menuOpen, setMenuOpen] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [openDropdown, setOpenDropdown] = useState(null);
    const navbarRef = useRef(null);
    const visibleLinks = LINKS.map((link) => {
        if (link.module && !isModuleVisible(link.module)) return null;
        if (!link.dropdown) return link;
        const dropdown = link.dropdown.filter((item) => !item.module || isModuleVisible(item.module));
        return dropdown.length ? { ...link, dropdown } : null;
    }).filter(Boolean);

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (navbarRef.current && !navbarRef.current.contains(event.target)) {
                setOpenDropdown(null);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const closeMenu = () => {
        setMenuOpen(false);
        setOpenDropdown(null);
    };

    return (
        <nav className={styles.navbar} ref={navbarRef}>
            <Link to="/" className={styles.brand} onClick={closeMenu}>
                <img src={siteConfig.branding?.logo_url || logo} alt="Logo de CONIITI" className={styles.logoImg} />
                <div className={styles.brandText}>
                    <span className={styles.brandName}>
                        <span className={styles.accent}>C</span>ONIITI
                    </span>
                    {theme.editionLabel && <span className={styles.brandEdition}>{theme.editionLabel}</span>}
                </div>
            </Link>

            <ul className={`${styles.links} ${menuOpen ? styles.linksOpen : ''}`}>
                {visibleLinks.map((link) => {
                    if (link.dropdown) {
                        const isActive = activePage === link.path || link.dropdown.some((subLink) => activePage === subLink.path);
                        const isOpen = openDropdown === link.name;

                        return (
                            <li key={link.name} className={styles.dropdownItem}>
                                <button
                                    className={`${styles.link} ${isActive ? styles.active : ''}`}
                                    onClick={(event) => {
                                        event.preventDefault();
                                        setOpenDropdown(isOpen ? null : link.name);
                                    }}
                                >
                                    {link.name}
                                    <FiChevronDown
                                        className={`${styles.chevron} ${isOpen ? styles.chevronOpen : ''}`}
                                        size={13}
                                    />
                                    {isActive && <span className={styles.activeDot} />}
                                </button>

                                {isOpen && (
                                    <ul className={styles.dropdown}>
                                        {link.dropdown.map((subLink) => (
                                            <li key={subLink.name}>
                                                <Link
                                                    to={subLink.path}
                                                    className={`${styles.dropdownLink} ${activePage === subLink.path ? styles.dropdownLinkActive : ''}`}
                                                    onClick={closeMenu}
                                                >
                                                    {subLink.icon === 'FiBookmark' && <FiBookmark size={13} />}
                                                    {subLink.name}
                                                    {user && subLink.icon === 'FiBookmark' && registeredCount > 0 && (
                                                        <span className={styles.badge}>{registeredCount}</span>
                                                    )}
                                                </Link>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </li>
                        );
                    }

                    return (
                        <li key={link.name}>
                            <Link
                                to={link.path}
                                className={`${styles.link} ${activePage === link.path ? styles.active : ''}`}
                                onClick={closeMenu}
                            >
                                {link.name}
                                {activePage === link.path && <span className={styles.activeDot} />}
                            </Link>
                        </li>
                    );
                })}
            </ul>

            <div className={styles.rightControls}>
                <div className={styles.searchWrapper}>
                    <FiSearch className={styles.searchIcon} />
                    <input
                        type="text"
                        placeholder="Buscar en CONIITI..."
                        className={styles.searchInput}
                        value={searchQuery}
                        onChange={(event) => setSearchQuery(event.target.value)}
                    />
                </div>

                <div className={styles.authWrapper}>
                    {user ? (
                        <div className={styles.userProfile}>
                            {user.role === 'superuser' && (
                                <>
                                    <Link to="/superusuario" className={styles.staffLink} onClick={closeMenu}>
                                        Panel general
                                    </Link>
                                    <Link to="/staff" className={styles.staffLink} onClick={closeMenu}>
                                        Panel de gestión
                                    </Link>
                                </>
                            )}
                            {user.role === 'staff' && (
                                <Link to="/staff" className={styles.staffLink} onClick={closeMenu}>
                                    Panel de gestión
                                </Link>
                            )}
                            <span className={styles.userName}>{user.full_name}</span>
                            <Link to="/perfil" className={styles.staffLink} onClick={closeMenu}>
                                Mi perfil
                            </Link>
                            <Link to="/mis-grupos" className={styles.staffLink} onClick={closeMenu}>
                                Mis grupos
                            </Link>
                            <button className={styles.logoutBtn} onClick={() => { logout(); navigate('/'); }}>
                                Cerrar sesión
                            </button>
                        </div>
                    ) : (
                        <button
                            className={styles.loginBtn}
                            onClick={() => navigate('/login')}
                        >
                            Iniciar sesión
                        </button>
                    )}
                </div>
            </div>

            <button
                className={`${styles.hamburger} ${menuOpen ? styles.hamburgerOpen : ''}`}
                onClick={() => setMenuOpen(!menuOpen)}
                aria-label="Menú"
            >
                {menuOpen ? <FiX size={22} /> : <FiMenu size={22} />}
            </button>
        </nav>
    );
}
