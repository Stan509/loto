document.addEventListener("DOMContentLoaded", () => {
    // Utilities
    const $ = (id) => document.getElementById(id);
    const $$ = (selector) => document.querySelectorAll(selector);
    
    console.log("[DEBUG] Gaboom Enterprise Engine Loaded");

    // Common Modal Logic
    const openModal = (modal, content) => {
        if (!modal || !content) return;
        modal.classList.remove("opacity-0", "pointer-events-none");
        content.classList.remove("scale-95");
        content.classList.add("scale-100");
        document.body.style.overflow = "hidden";
        lucide.createIcons();
    };

    const closeModal = (modal, content) => {
        if (!modal || !content) return;
        modal.classList.add("opacity-0", "pointer-events-none");
        content.classList.remove("scale-100");
        content.classList.add("scale-95");
        document.body.style.overflow = "";
    };

    const setDisplay = (id, value) => {
        const el = $(id);
        if (el) el.style.display = value;
    };

    // --- Signup Logic (Multi-step) ---
    const signupModal = $("signupModal");
    const signupModalContent = $("signupModalContent");
    const signupModalBackdrop = $("signupModalBackdrop");
    const closeSignupModalBtn = $("closeSignupModalBtn");
    const signupForm = $("signupForm");

    // Multi-step navigation
    const signupStep1 = $("signupStep1");
    const signupStep2 = $("signupStep2");
    const signupStep3 = $("signupStep3");
    const nextToStep2 = $("nextToStep2");
    const nextToStep3 = $("nextToStep3");
    const backToStep1 = $("backToStep1");
    const backToStep2 = $("backToStep2");

    $$("[data-open-signup]").forEach(btn => {
        btn.addEventListener("click", () => {
            setDisplay("signupStepForm", "block");
            setDisplay("signupStepLoading", "none");
            setDisplay("signupStepError", "none");
            signupForm?.reset();
            // Reset to step 1
            if (signupStep1) signupStep1.style.display = "block";
            if (signupStep2) signupStep2.style.display = "none";
            if (signupStep3) signupStep3.style.display = "none";
            openModal(signupModal, signupModalContent);
        });
    });

    closeSignupModalBtn?.addEventListener("click", () => closeModal(signupModal, signupModalContent));
    signupModalBackdrop?.addEventListener("click", () => closeModal(signupModal, signupModalContent));

    // Step 1 -> Step 2
    nextToStep2?.addEventListener("click", () => {
        const email = signupForm?.querySelector('input[name="email"]')?.value;
        const phone = signupForm?.querySelector('input[name="phone"]')?.value;
        
        if (!email || !phone) {
            alert("Veuillez remplir tous les champs.");
            return;
        }
        
        if (signupStep1) signupStep1.style.display = "none";
        if (signupStep2) signupStep2.style.display = "block";
    });

    // Step 2 -> Step 1
    backToStep1?.addEventListener("click", () => {
        if (signupStep2) signupStep2.style.display = "none";
        if (signupStep1) signupStep1.style.display = "block";
    });

    // Step 2 -> Step 3
    nextToStep3?.addEventListener("click", () => {
        const borletteName = signupForm?.querySelector('input[name="borlette_name"]')?.value;
        const adresse = signupForm?.querySelector('input[name="adresse"]')?.value;
        const slogan = signupForm?.querySelector('input[name="slogan"]')?.value;
        
        if (!borletteName || !adresse || !slogan) {
            alert("Veuillez remplir tous les champs.");
            return;
        }
        
        if (signupStep2) signupStep2.style.display = "none";
        if (signupStep3) signupStep3.style.display = "block";
    });

    // Step 3 -> Step 2
    backToStep2?.addEventListener("click", () => {
        if (signupStep3) signupStep3.style.display = "none";
        if (signupStep2) signupStep2.style.display = "block";
    });

    // Submit form
    signupForm?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const fd = new FormData(signupForm);
        
        const password = fd.get("password");
        const passwordConfirm = fd.get("password_confirm");
        
        if (!password || password !== passwordConfirm) {
            alert("Les mots de passe ne correspondent pas.");
            return;
        }

        setDisplay("signupStepForm", "none");
        setDisplay("signupStepLoading", "flex");

        try {
            const payload = {
                username: fd.get("username"),
                email: fd.get("email"),
                phone: fd.get("phone"),
                borlette_name: fd.get("borlette_name"),
                adresse: fd.get("adresse"),
                slogan: fd.get("slogan"),
                password: password,
                promo_code: fd.get("promo_code")
            };

            const res = await fetch("/api/signup/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await res.json().catch(() => ({}));

            if (!res.ok) {
                throw new Error(data?.message || "Erreur d'inscription.");
            }

            // Succès - gérer la réponse avec redirect_url
            setDisplay("signupStepLoading", "none");
            setDisplay("signupStepForm", "none");
            
            // Afficher un message de succès
            const errText = $("signupErrorText");
            const errTitle = $("signupStepError").querySelector("h3");
            
            if (errTitle) errTitle.textContent = "✅ Inscription réussie !";
            if (errText) {
                errText.textContent = "Inscription réussie !\n\nVous allez être connecté automatiquement...";
                errText.style.color = "#10b981"; // Green color
            }
            setDisplay("signupStepError", "block");
            
            // Rediriger vers l'URL de connexion automatique ou la page de login
            const redirectUrl = data?.redirect_url || "/portal/login/";
            setTimeout(() => {
                window.location.href = redirectUrl;
            }, 2000);
        } catch (err) {
            setDisplay("signupStepLoading", "none");
            setDisplay("signupStepError", "block");
            const errText = $("signupErrorText");
            if (errText) errText.textContent = err.message;
        }
    });

    $("retrySignupBtn")?.addEventListener("click", () => {
        setDisplay("signupStepError", "none");
        setDisplay("signupStepForm", "block");
        // Reset to step 1
        if (signupStep1) signupStep1.style.display = "block";
        if (signupStep2) signupStep2.style.display = "none";
        if (signupStep3) signupStep3.style.display = "none";
    });

    // --- Affiliate Logic ---
    const affModal = $("affiliateModal");
    const affContent = $("affiliateModalContent");
    const affForm = $("affiliateForm");

    $("openAffiliateModalBtn")?.addEventListener("click", () => {
        setDisplay("affiliateStepForm", "block");
        setDisplay("affiliateStepLoading", "none");
        setDisplay("affiliateStepResult", "none");
        affForm?.reset();
        openModal(affModal, affContent);
    });

    $("closeAffiliateModalBtn")?.addEventListener("click", () => closeModal(affModal, affContent));
    $("affiliateModalBackdrop")?.addEventListener("click", () => closeModal(affModal, affContent));

    affForm?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const fd = new FormData(affForm);

        if (fd.get("password") !== fd.get("password_confirm")) {
            alert("Les mots de passe ne correspondent pas.");
            return;
        }

        setDisplay("affiliateStepForm", "none");
        setDisplay("affiliateStepLoading", "flex");

        try {
            const res = await fetch("/api/affiliate/register/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    full_name: fd.get("full_name"),
                    email: fd.get("email"),
                    phone: fd.get("phone"),
                    username: fd.get("username"),
                    password: fd.get("password")
                })
            });

            const data = await res.json().catch(() => ({}));
            setDisplay("affiliateStepLoading", "none");
            setDisplay("affiliateStepResult", "block");

            if (res.ok && data.success) {
                $("affiliateSuccessIcon").classList.remove("hidden");
                $("affiliateErrorIcon").classList.add("hidden");
                // Forcer la redirection vers le dashboard affilié
                const redirectUrl = "/affiliate/dashboard/";
                console.log("[AFFILIATE] Success! Redirecting to:", redirectUrl, "API response:", data);
                setTimeout(() => { 
                    console.log("[AFFILIATE] Navigating now to:", redirectUrl);
                    window.location.replace(redirectUrl);  // replace() au lieu de href pour éviter l'historique
                }, 2000);
            } else {
                throw new Error(data.error || "Échec de l'enregistrement.");
            }
        } catch (err) {
            setDisplay("affiliateStepLoading", "none");
            setDisplay("affiliateStepResult", "block");
            $("affiliateSuccessIcon").classList.add("hidden");
            $("affiliateErrorIcon").classList.remove("hidden");
            const errText = $("affiliateErrorText");
            if (errText) errText.textContent = err.message;
        }
    });

    $("retryAffiliateBtn")?.addEventListener("click", () => {
        setDisplay("affiliateStepResult", "none");
        setDisplay("affiliateStepForm", "block");
    });

    // Global: Close on Escape
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeModal(signupModal, signupModalContent);
            closeModal(affModal, affContent);
        }
    });

    // Precision Reveal on Scroll
    const precisionReveal = () => {
        const reveals = document.querySelectorAll(".reveal");
        reveals.forEach(el => {
            const windowHeight = window.innerHeight;
            const elementTop = el.getBoundingClientRect().top;
            if (elementTop < windowHeight - 50) {
                el.classList.add("active");
            }
        });
    };

    window.addEventListener("scroll", precisionReveal);
    precisionReveal();

    // --- Pricing Calculator ---
    const agentCountInput = $("agentCountInput");
    const promoCodeCheck = $("promoCodeCheck");
    const priceWithoutPromo = $("priceWithoutPromo");
    const priceWithPromo = $("priceWithPromo");
    const savingsAmount = $("savingsAmount");

    if (agentCountInput && promoCodeCheck) {
        const formatNumber = (num) => num.toLocaleString('fr-FR');

        const calculatePrice = () => {
            const agents = parseInt(agentCountInput.value) || 0;
            const hasPromo = promoCodeCheck.checked;

            // Prix de base
            const baseActivation = 12500;
            const baseAgent = 1250;
            const baseTotal = baseActivation + (baseAgent * agents);

            // Réductions
            const discountActivation = hasPromo ? 500 : 0;
            const discountPerAgent = hasPromo ? 50 : 0;
            const discountAgents = discountPerAgent * agents;
            const totalDiscount = discountActivation + discountAgents;

            // Totaux
            const totalWithPromo = baseTotal - totalDiscount;

            // Mise à jour des affichages
            if (priceWithoutPromo) {
                priceWithoutPromo.textContent = formatNumber(baseTotal) + " GDS";
            }
            if (priceWithPromo) {
                priceWithPromo.textContent = formatNumber(totalWithPromo) + " GDS";
            }
            if (savingsAmount) {
                savingsAmount.textContent = formatNumber(totalDiscount);
            }
        };

        agentCountInput.addEventListener("input", calculatePrice);
        promoCodeCheck.addEventListener("change", calculatePrice);

        // Calcul initial
        calculatePrice();
    }

    lucide.createIcons();
});
