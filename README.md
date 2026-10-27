    # SigmaOS-theme-registry

    Theme registry & index

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/linuxmint/mint-themes
- https://github.com/omacom/omarchy-theme-registry

    ## Design principles applied
    - **Plan Before Act**
- **Information Hiding**
- **Fail-Fast**
- **Defensive Programming**
- **KISS**
- **Deterministic Testing**

    ## Usage
    Verbs: `search, install-plan, rate, index`

    ```
    $ sigma-theme-market search dark --tag mint
mint-y-dark  Mint-Y-Dark  4.5 (120 votes)
$ sigma-theme-market install-plan registry.json mint-y-dark \
    --installed mint-y=1.2.0 --target ~/.themes
fetch  https://themes.sigmaos.dev/mint-y-dark-2.0.0.tar.xz
verify sha256:<hash>
$ sigma-theme-market rate ratings.json mint-y-dark 5
$ sigma-theme-market index ./submitted --out registry.json

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
