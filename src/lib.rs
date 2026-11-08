//! SigmaOS-theme-registry — Theme registry for SigmaOS.

/// Theme variant
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ThemeVariant { Light, Dark, Auto }

/// Theme manifest
#[derive(Debug, Clone)]
pub struct ThemeManifest {
    pub name: String,
    pub description: String,
    pub is_dark: bool,
    pub accent_hex: String,
    pub variant: ThemeVariant,
    pub author: String,
    pub version: String,
    pub tags: Vec<String>,
}

impl ThemeManifest {
    /// Create new manifest
    pub fn new(name: &str, is_dark: bool, accent: &str) -> Self {
        Self {
            name: name.into(),
            description: String::new(),
            is_dark,
            accent_hex: accent.into(),
            variant: if is_dark { ThemeVariant::Dark } else { ThemeVariant::Light },
            author: String::new(),
            version: "1.0.0".into(),
            tags: vec![],
        }
    }

    /// Set description
    pub fn set_description(&mut self, desc: &str) {
        self.description = desc.into();
    }

    /// Set author
    pub fn set_author(&mut self, author: &str) {
        self.author = author.into();
    }

    /// Set version
    pub fn set_version(&mut self, version: &str) {
        self.version = version.into();
    }

    /// Add tag
    pub fn add_tag(&mut self, tag: &str) {
        self.tags.push(tag.into());
    }

    /// Check if matches query
    pub fn matches(&self, query: &str) -> bool {
        let q = query.to_lowercase();
        self.name.to_lowercase().contains(&q) ||
        self.description.to_lowercase().contains(&q) ||
        self.tags.iter().any(|t| t.to_lowercase().contains(&q))
    }
}

/// Theme registry
#[derive(Debug, Default)]
pub struct ThemeRegistry {
    themes: Vec<ThemeManifest>,
    active_theme: String,
}

impl ThemeRegistry {
    pub fn new() -> Self { Self::default() }

    /// Register theme
    pub fn register(&mut self, theme: ThemeManifest) -> bool {
        if self.themes.iter().any(|t| t.name == theme.name) { return false; }
        self.themes.push(theme);
        true
    }

    /// Register simple theme
    pub fn register_simple(&mut self, name: &str, dark: bool, accent: &str) {
        self.register(ThemeManifest::new(name, dark, accent));
    }

    /// Activate theme
    pub fn set_active(&mut self, name: &str) -> bool {
        if self.themes.iter().any(|t| t.name == name) {
            self.active_theme = name.into();
            return true;
        }
        false
    }

    /// Get active theme name
    pub fn get_active(&self) -> &str { &self.active_theme }

    /// Get active theme
    pub fn active_theme(&self) -> Option<&ThemeManifest> {
        self.themes.iter().find(|t| t.name == self.active_theme)
    }

    /// List themes
    pub fn list(&self) -> &[ThemeManifest] { &self.themes }

    /// Dark themes
    pub fn dark_themes(&self) -> Vec<&ThemeManifest> {
        self.themes.iter().filter(|t| t.is_dark).collect()
    }

    /// Light themes
    pub fn light_themes(&self) -> Vec<&ThemeManifest> {
        self.themes.iter().filter(|t| !t.is_dark).collect()
    }

    /// Search themes
    pub fn search(&self, query: &str) -> Vec<&ThemeManifest> {
        self.themes.iter().filter(|t| t.matches(query)).collect()
    }

    /// Remove theme
    pub fn remove(&mut self, name: &str) -> bool {
        let before = self.themes.len();
        self.themes.retain(|t| t.name != name);
        if self.active_theme == name { self.active_theme.clear(); }
        self.themes.len() < before
    }

    /// Theme count
    pub fn count(&self) -> usize { self.themes.len() }

    /// Default themes
    pub fn with_defaults() -> Self {
        let mut reg = Self::new();
        reg.register_simple("SigmaOS-Dark", true, "#7c3aed");
        reg.register_simple("SigmaOS-Light", false, "#7c3aed");
        reg.register_simple("Nord", true, "#88c0d0");
        reg.register_simple("Dracula", true, "#bd93f9");
        reg.register_simple("Gruvbox", true, "#fe8019");
        reg.set_active("SigmaOS-Dark");
        reg
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_theme_variant() {
        let variants = vec![ThemeVariant::Light, ThemeVariant::Dark, ThemeVariant::Auto];
        assert_eq!(variants.len(), 3);
    }

    #[test]
    fn test_manifest_creation() {
        let theme = ThemeManifest::new("Nord", true, "#88c0d0");
        assert_eq!(theme.name, "Nord");
        assert!(theme.is_dark);
        assert_eq!(theme.variant, ThemeVariant::Dark);
        assert_eq!(theme.version, "1.0.0");
    }

    #[test]
    fn test_manifest_fields() {
        let mut theme = ThemeManifest::new("T", false, "#fff");
        theme.set_description("A theme");
        theme.set_author("Dev");
        theme.set_version("2.0");
        theme.add_tag("dark");
        theme.add_tag("minimal");
        
        assert_eq!(theme.description, "A theme");
        assert_eq!(theme.author, "Dev");
        assert_eq!(theme.version, "2.0");
        assert_eq!(theme.tags.len(), 2);
    }

    #[test]
    fn test_manifest_matches() {
        let mut theme = ThemeManifest::new("Nord Dark", true, "#88c0d0");
        theme.add_tag("arctic");
        
        assert!(theme.matches("nord"));
        assert!(theme.matches("dark"));
        assert!(theme.matches("arctic"));
        assert!(!theme.matches("light"));
    }

    #[test]
    fn test_registry_register() {
        let mut reg = ThemeRegistry::new();
        assert!(reg.register(ThemeManifest::new("a", true, "#fff")));
        assert!(!reg.register(ThemeManifest::new("a", false, "#000"))); // dup
        assert_eq!(reg.count(), 1);
    }

    #[test]
    fn test_registry_activate() {
        let mut reg = ThemeRegistry::new();
        reg.register_simple("dark", true, "#000");
        reg.register_simple("light", false, "#fff");
        
        assert!(reg.set_active("dark"));
        assert_eq!(reg.get_active(), "dark");
        assert!(reg.active_theme().is_some());
        assert!(!reg.set_active("missing"));
    }

    #[test]
    fn test_dark_light_filter() {
        let reg = ThemeRegistry::with_defaults();
        assert_eq!(reg.dark_themes().len(), 4); // Dark, Nord, Dracula, Gruvbox
        assert_eq!(reg.light_themes().len(), 1); // Light
    }

    #[test]
    fn test_search() {
        let reg = ThemeRegistry::with_defaults();
        let results = reg.search("sigma");
        assert_eq!(results.len(), 2);
        let nord = reg.search("nord");
        assert_eq!(nord.len(), 1);
    }

    #[test]
    fn test_with_defaults() {
        let reg = ThemeRegistry::with_defaults();
        assert_eq!(reg.count(), 5);
        assert_eq!(reg.get_active(), "SigmaOS-Dark");
    }
}
