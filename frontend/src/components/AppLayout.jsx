import { useEffect, useRef, useState } from "react";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import MenuIcon from "@mui/icons-material/Menu";
import CheckIcon from "@mui/icons-material/Check";
import LanguageOutlinedIcon from "@mui/icons-material/LanguageOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import {
  AppBar,
  Box,
  Button,
  Container,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Toolbar,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme
} from "@mui/material";
import { Link as RouterLink, useLocation } from "react-router-dom";
import { useLocale } from "../i18n/locale";

const navItems = [
  { labelKey: "nav_announcements", path: "/announcements", roles: ["user", "admin"] },
  { labelKey: "nav_models", path: "/usage-examples", roles: ["user", "admin"] },
  { labelKey: "nav_apply", path: "/apply", roles: ["user", "admin"] },
  { labelKey: "nav_api_keys", path: "/api-keys", roles: ["user", "admin"] },
  { labelKey: "nav_usage", path: "/usage", roles: ["user", "admin"] },
  { labelKey: "nav_whitelists", path: "/whitelists", roles: ["admin"] },
  { labelKey: "nav_limit_strategies", path: "/limit-strategies", roles: ["admin"] },
  { labelKey: "nav_admins", path: "/users", roles: ["admin"] },
  { labelKey: "nav_dashboard", path: "/admin-dashboard", roles: ["admin"] },
  { labelKey: "nav_operation_logs", path: "/operation-audit-logs", roles: ["admin"] },
  { labelKey: "nav_institute_view", path: "/institute-view", roles: ["admin"] }
];

function isNavItemActive(pathname, itemPath) {
  return pathname === itemPath || pathname.startsWith(`${itemPath}/`);
}

function setScrollLeft(container, left) {
  if (!container) return;
  if (typeof container.scrollTo === "function") {
    container.scrollTo({ left, behavior: "smooth" });
    return;
  }
  container.scrollLeft = left;
}

export default function AppLayout({
  children,
  auth,
  onChangeLocale = () => {},
  onLogout = () => {},
  logoutInProgress = false
}) {
  const location = useLocation();
  const { locale, t } = useLocale();
  const theme = useTheme();
  const useDrawerNav = useMediaQuery(theme.breakpoints.down("md"));
  const [localeMenuAnchor, setLocaleMenuAnchor] = useState(null);
  const [navDrawerOpen, setNavDrawerOpen] = useState(false);
  const [navHasOverflow, setNavHasOverflow] = useState(false);
  const [canScrollNavLeft, setCanScrollNavLeft] = useState(false);
  const [canScrollNavRight, setCanScrollNavRight] = useState(false);
  const [currentNavItemIndex, setCurrentNavItemIndex] = useState(0);
  const navScrollRef = useRef(null);
  const navTrackRef = useRef(null);
  const navItemRefs = useRef([]);
  const visibleNavItems = navItems.filter((item) => item.roles.includes(auth.role));
  const localeMenuOpen = Boolean(localeMenuAnchor);
  const logoSrc = `${import.meta.env.BASE_URL}favicon.svg`;
  const isAdminDesktopNav = auth.role === "admin" && !useDrawerNav;

  function getItemStart(item) {
    const track = navTrackRef.current;

    if (!item) return 0;

    return (track?.offsetLeft ?? 0) + item.offsetLeft;
  }

  function getItemEnd(item) {
    return getItemStart(item) + item.offsetWidth;
  }

  function getNavMetrics() {
    const container = navScrollRef.current;
    const items = navItemRefs.current.filter(Boolean);

    if (!container || items.length === 0) {
      return null;
    }

    const containerLeft = container.scrollLeft;
    const containerRight = containerLeft + container.clientWidth;
    const maxScrollLeft = Math.max(container.scrollWidth - container.clientWidth, 0);
    const lastItem = items.at(-1);
    const firstItem = items[0];
    const hasOverflow = maxScrollLeft > 1;
    const firstVisibleIndex = items.findIndex((item) => getItemEnd(item) > containerLeft + 1);
    const lastVisibleIndex = items.findLastIndex((item) => getItemStart(item) < containerRight - 1);

    return {
      container,
      items,
      containerLeft,
      containerRight,
      maxScrollLeft,
      hasOverflow,
      firstVisibleIndex: firstVisibleIndex === -1 ? 0 : firstVisibleIndex,
      lastVisibleIndex: lastVisibleIndex === -1 ? items.length - 1 : lastVisibleIndex,
      firstItemFullyVisible: getItemStart(firstItem) >= containerLeft - 1,
      lastItemFullyVisible: getItemEnd(lastItem) <= containerRight + 1
    };
  }

  function syncNavOverflowState() {
    const metrics = getNavMetrics();

    if (!metrics) {
      setNavHasOverflow(false);
      setCanScrollNavLeft(false);
      setCanScrollNavRight(false);
      setCurrentNavItemIndex(0);
      return;
    }

    setNavHasOverflow(metrics.hasOverflow);
    setCanScrollNavLeft(metrics.hasOverflow && metrics.containerLeft > 1);
    setCanScrollNavRight(metrics.hasOverflow && metrics.containerLeft < metrics.maxScrollLeft - 1);
    setCurrentNavItemIndex((previousIndex) => {
      if (!metrics.hasOverflow) return 0;
      return Math.min(
        Math.max(previousIndex, metrics.firstVisibleIndex),
        metrics.lastVisibleIndex
      );
    });
  }

  function scrollNavItemIntoView(index, inline = "start") {
    const metrics = getNavMetrics();
    const item = navItemRefs.current[index];

    if (!metrics || !item) return;

    if (index === 0) {
      setScrollLeft(metrics.container, 0);
      return;
    }

    if (index === visibleNavItems.length - 1) {
      setScrollLeft(metrics.container, metrics.maxScrollLeft);
      return;
    }

    const itemStart = getItemStart(item);
    const itemEnd = getItemEnd(item);
    let nextScrollLeft = metrics.containerLeft;

    if (inline === "nearest") {
      if (itemStart < metrics.containerLeft) {
        nextScrollLeft = itemStart;
      } else if (itemEnd > metrics.containerRight) {
        nextScrollLeft = itemEnd - metrics.container.clientWidth;
      }
    } else {
      nextScrollLeft = itemStart;
    }

    const clampedScrollLeft = Math.max(0, Math.min(nextScrollLeft, metrics.maxScrollLeft));
    setScrollLeft(metrics.container, clampedScrollLeft);
  }

  function ensureActiveNavItemVisible() {
    const activeIndex = visibleNavItems.findIndex((item) => isNavItemActive(location.pathname, item.path));

    if (activeIndex === -1) return;

    setCurrentNavItemIndex(activeIndex);
    scrollNavItemIntoView(activeIndex, "nearest");
  }

  function scrollToPreviousNavItem() {
    const metrics = getNavMetrics();

    if (!metrics) return;

    const targetIndex = Math.max(metrics.firstVisibleIndex - 1, 0);

    setCurrentNavItemIndex(targetIndex);
    scrollNavItemIntoView(targetIndex, "nearest");
  }

  function scrollToNextNavItem() {
    const metrics = getNavMetrics();

    if (!metrics) return;

    const targetIndex = Math.min(metrics.lastVisibleIndex + 1, visibleNavItems.length - 1);

    setCurrentNavItemIndex(targetIndex);
    scrollNavItemIntoView(targetIndex, "nearest");
  }

  function openNavDrawer() {
    setNavDrawerOpen(true);
  }

  function closeNavDrawer() {
    setNavDrawerOpen(false);
  }

  function openLocaleMenu(event) {
    setLocaleMenuAnchor(event.currentTarget);
  }

  function closeLocaleMenu() {
    setLocaleMenuAnchor(null);
  }

  function selectLocale(nextLocale) {
    onChangeLocale(nextLocale);
    closeLocaleMenu();
  }

  function selectLocaleFromDrawer(nextLocale) {
    onChangeLocale(nextLocale);
    closeNavDrawer();
  }

  function handleDrawerLogout() {
    closeNavDrawer();
    onLogout();
  }

  useEffect(() => {
    navItemRefs.current = navItemRefs.current.slice(0, visibleNavItems.length);
  }, [visibleNavItems.length]);

  useEffect(() => {
    if (!isAdminDesktopNav) {
      setNavHasOverflow(false);
      setCanScrollNavLeft(false);
      setCanScrollNavRight(false);
      setCurrentNavItemIndex(0);
      return undefined;
    }

    const container = navScrollRef.current;

    if (!container) return undefined;

    function syncNavStateWithActiveItem() {
      syncNavOverflowState();
      ensureActiveNavItemVisible();
      syncNavOverflowState();
    }

    function handleNavScroll() {
      syncNavOverflowState();
    }

    syncNavStateWithActiveItem();
    container.addEventListener("scroll", handleNavScroll, { passive: true });
    window.addEventListener("resize", syncNavStateWithActiveItem);

    return () => {
      container.removeEventListener("scroll", handleNavScroll);
      window.removeEventListener("resize", syncNavStateWithActiveItem);
    };
  }, [auth.role, isAdminDesktopNav, locale, location.pathname, visibleNavItems.length]);

  return (
    <Box
      sx={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #f4f7fb 0%, #e9eef7 100%)",
        display: "flex",
        flexDirection: "column"
      }}
    >
      <AppBar position="static" elevation={0}>
        <Toolbar sx={{ gap: 1.5, minWidth: 0 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, minWidth: 0, flexShrink: 0 }}>
            <Box
              component="img"
              src={logoSrc}
              alt="AS API Console logo"
              sx={{ width: 32, height: 32, flexShrink: 0 }}
            />
            <Typography variant="h6" sx={{ minWidth: 0, fontSize: { xs: "1.18rem", md: "1.28rem" } }}>
              AS API Console
            </Typography>
          </Box>
          {useDrawerNav ? (
            <Box sx={{ ml: "auto", display: "flex", alignItems: "center", flexShrink: 0 }}>
              <Tooltip title={t("nav_open_menu", locale === "zh-TW" ? "開啟導覽選單" : "Open navigation menu")}>
                <IconButton
                  aria-label={t("nav_open_menu", locale === "zh-TW" ? "開啟導覽選單" : "Open navigation menu")}
                  color="inherit"
                  onClick={openNavDrawer}
                >
                  <MenuIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          ) : (
            <>
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  minWidth: 0,
                  flex: 1,
                  overflow: "hidden"
                }}
              >
                {isAdminDesktopNav && navHasOverflow ? (
                  <IconButton
                    aria-label="上一個導覽項目"
                    color="inherit"
                    onClick={scrollToPreviousNavItem}
                    disabled={!canScrollNavLeft}
                    sx={{ flexShrink: 0, mr: 0.25 }}
                  >
                    <ChevronLeftIcon fontSize="small" />
                  </IconButton>
                ) : null}
                <Box
                  ref={navScrollRef}
                  data-testid="desktop-nav-scroll"
                  sx={{
                    minWidth: 0,
                    flex: 1,
                    overflowX: isAdminDesktopNav ? "auto" : "hidden",
                    overflowY: "hidden",
                    scrollBehavior: "smooth",
                    scrollbarWidth: "none",
                    "&::-webkit-scrollbar": {
                      display: "none"
                    }
                  }}
                >
                  <Box
                    ref={navTrackRef}
                    data-testid="desktop-nav-track"
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 0.25,
                      width: "max-content",
                      minWidth: "100%",
                      mx: "auto"
                    }}
                  >
                    {visibleNavItems.map((item, index) => (
                      <Button
                        key={item.labelKey}
                        ref={(node) => {
                          navItemRefs.current[index] = node;
                        }}
                        data-testid={`desktop-nav-item-${index}`}
                        component={RouterLink}
                        to={item.path}
                        color={isNavItemActive(location.pathname, item.path) ? "secondary" : "inherit"}
                        sx={{
                          minWidth: "auto",
                          px: { md: 1, lg: 1.3, xl: 1.6 },
                          fontSize: { md: "16px", lg: "17px", xl: "18px" },
                          whiteSpace: "nowrap",
                          flexShrink: 0
                        }}
                      >
                        {t(item.labelKey)}
                      </Button>
                    ))}
                  </Box>
                </Box>
                {isAdminDesktopNav && navHasOverflow ? (
                  <IconButton
                    aria-label="下一個導覽項目"
                    color="inherit"
                    onClick={scrollToNextNavItem}
                    disabled={!canScrollNavRight}
                    sx={{ flexShrink: 0, ml: 0.25 }}
                  >
                    <ChevronRightIcon fontSize="small" />
                  </IconButton>
                ) : null}
              </Box>
              <Box sx={{ display: "flex", alignItems: "center", ml: 0.5, flexShrink: 0 }}>
                <Tooltip title={locale === "zh-TW" ? "語言" : "Language"}>
                  <IconButton
                    aria-label={locale === "zh-TW" ? "語言" : "Language"}
                    color="inherit"
                    onClick={openLocaleMenu}
                    sx={{ mr: 0.5 }}
                  >
                    <LanguageOutlinedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Menu
                  anchorEl={localeMenuAnchor}
                  open={localeMenuOpen}
                  onClose={closeLocaleMenu}
                  anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
                  transformOrigin={{ vertical: "top", horizontal: "right" }}
                >
                  <MenuItem selected={locale === "zh-TW"} onClick={() => selectLocale("zh-TW")}>
                    <Box sx={{ minWidth: 44 }}>{t("lang_zh", "中文")}</Box>
                    <Box
                      sx={{ width: 20, display: "inline-flex", justifyContent: "center", ml: 1 }}
                      data-testid="locale-check-zh-TW"
                    >
                      {locale === "zh-TW" ? <CheckIcon fontSize="small" /> : null}
                    </Box>
                  </MenuItem>
                  <MenuItem selected={locale === "en"} onClick={() => selectLocale("en")}>
                    <Box sx={{ minWidth: 44 }}>{t("lang_en", "EN")}</Box>
                    <Box
                      sx={{ width: 20, display: "inline-flex", justifyContent: "center", ml: 1 }}
                      data-testid="locale-check-en"
                    >
                      {locale === "en" ? <CheckIcon fontSize="small" /> : null}
                    </Box>
                  </MenuItem>
                </Menu>
                <Tooltip title={locale === "zh-TW" ? "登出" : "Logout"}>
                  <IconButton
                    aria-label={locale === "zh-TW" ? "登出" : "Logout"}
                    color="inherit"
                    onClick={onLogout}
                    disabled={logoutInProgress}
                  >
                    <LogoutOutlinedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            </>
          )}
        </Toolbar>
      </AppBar>
      <Drawer
        anchor="left"
        open={navDrawerOpen}
        onClose={closeNavDrawer}
      >
        <Box
          sx={{ width: { xs: 280, sm: 320 }, display: "flex", flexDirection: "column", height: "100%" }}
          role="presentation"
        >
          <Box sx={{ px: 2, py: 2 }}>
            <Typography variant="h6" sx={{ fontSize: { xs: "1.22rem", sm: "1.28rem" } }}>
              {t("nav_menu", locale === "zh-TW" ? "導覽選單" : "Navigation")}
            </Typography>
          </Box>
          <Divider />
          <List sx={{ py: 0.5 }}>
            {visibleNavItems.map((item) => (
              <ListItemButton
                key={item.labelKey}
                component={RouterLink}
                to={item.path}
                selected={isNavItemActive(location.pathname, item.path)}
                onClick={closeNavDrawer}
                sx={{ py: 1.1 }}
              >
                <ListItemText
                  primary={t(item.labelKey)}
                  primaryTypographyProps={{ fontSize: { xs: "1.08rem", sm: "1.12rem" }, fontWeight: 500 }}
                />
              </ListItemButton>
            ))}
          </List>
          <Divider sx={{ mt: "auto" }} />
          <List sx={{ py: 0.5 }}>
            <ListItemButton
              selected={locale === "zh-TW"}
              onClick={() => selectLocaleFromDrawer("zh-TW")}
              aria-label={t("nav_lang_zh", locale === "zh-TW" ? "切換語言為中文" : "Switch language to Chinese")}
              sx={{ py: 1.1 }}
            >
              <ListItemText
                primary={t("lang_zh", "中文")}
                primaryTypographyProps={{ fontSize: { xs: "1.08rem", sm: "1.12rem" }, fontWeight: 500 }}
              />
              {locale === "zh-TW" ? <CheckIcon fontSize="small" /> : null}
            </ListItemButton>
            <ListItemButton
              selected={locale === "en"}
              onClick={() => selectLocaleFromDrawer("en")}
              aria-label={t("nav_lang_en", locale === "zh-TW" ? "切換語言為英文" : "Switch language to English")}
              sx={{ py: 1.1 }}
            >
              <ListItemText
                primary={t("lang_en", "EN")}
                primaryTypographyProps={{ fontSize: { xs: "1.08rem", sm: "1.12rem" }, fontWeight: 500 }}
              />
              {locale === "en" ? <CheckIcon fontSize="small" /> : null}
            </ListItemButton>
            <ListItemButton
              onClick={handleDrawerLogout}
              disabled={logoutInProgress}
              aria-label={locale === "zh-TW" ? "登出" : "Logout"}
              sx={{ py: 1.1 }}
            >
              <ListItemIcon sx={{ minWidth: 36 }}>
                <LogoutOutlinedIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText
                primary={locale === "zh-TW" ? "登出" : "Logout"}
                primaryTypographyProps={{ fontSize: { xs: "1.08rem", sm: "1.12rem" }, fontWeight: 500 }}
              />
            </ListItemButton>
          </List>
        </Box>
      </Drawer>
      <Container maxWidth={false} sx={{ py: { xs: 2, md: 2.5 }, px: { xs: 2, md: 3 }, display: "flex", flex: 1, minHeight: 0, overflow: "hidden" }}>
        <Box sx={{ maxWidth: 1840, mx: "auto", width: "100%", display: "flex", flexDirection: "column", gap: 2, flex: 1, minHeight: 0, overflow: "hidden" }}>
          {children}
        </Box>
      </Container>
    </Box>
  );
}
