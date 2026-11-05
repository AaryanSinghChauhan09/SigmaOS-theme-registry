#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ThemeManifest {
    pub name: String,
    pub is_dark: bool,
    pub accent_hex: String,
}

#[derive(Debug, Default)]
pub struct ThemeRegistry {
    themes: Vec<ThemeManifest>,
    active_theme: String,
}

impl ThemeRegistry {
    pub fn new() -> Self { Self { themes: Vec::new(), active_theme: String::new() } }
    pub fn register(&mut self, name: &str, dark: bool, accent: &str) {
        self.themes.push(ThemeManifest { name: name.into(), is_dark: dark, accent_hex: accent.into() });
    }
    pub fn set_active(&mut self, name: &str) {
        self.active_theme = name.into();
    }
    pub fn get_active(&self) -> &str { &self.active_theme }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_theme_registry_aaa() {
        // Arrange
        let mut reg = ThemeRegistry::new();
        reg.register("SigmaOS-Nord", true, "#88c0d0");
        // Act
        reg.set_active("SigmaOS-Nord");
        // Assert
        assert_eq!(reg.get_active(), "SigmaOS-Nord");
    }
}
