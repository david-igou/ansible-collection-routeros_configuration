COLLECTION_NAMESPACE := david_igou
COLLECTION_NAME      := routeros_configuration
COLLECTION           := $(COLLECTION_NAMESPACE).$(COLLECTION_NAME)
COLLECTION_VERSION   := $(shell grep '^version:' galaxy.yml | awk '{print $$2}')

MOLECULE_SCENARIOS := chr

# PROVISIONER picks which mp.<backend> block a scenario uses when its inventory
# declares more than one. The chr scenario declares only qemu, so leaving this
# unset is correct — molecule_provisioners auto-selects. Override only for
# multi-backend scenarios (e.g. `PROVISIONER=qemu make molecule SCENARIO=chr`).

# Scenarios live at extensions/molecule/<scenario>/molecule.yml — point molecule
# at that layout via MOLECULE_GLOB so the `molecule` target works from the
# collection root and auto-discovers the shared base config at
# extensions/molecule/config.yml (which only fires from the collection root).
export MOLECULE_GLOB := extensions/molecule/*/molecule.yml

# The dev shell may export ANSIBLE_INVENTORY for ad-hoc runs; it leaks into
# molecule's subprocess and overrides per-scenario inventory. Strip it.
unexport ANSIBLE_INVENTORY

.PHONY: help install molecule test collection-build collection-install clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime collection dependencies (community.routeros, ansible.netcommon)
	ansible-galaxy collection install -r requirements.yml

# `molecule` depends on `install` so a single `make molecule` resolves all
# collections the scenario needs: runtime deps here, and the pinned provisioner
# via molecule's own `dependency` step (extensions/molecule/config.yml ->
# requirements-test.yml). No manual ansible-galaxy calls required.
molecule: install ## Run molecule test (SCENARIO=<name> for one, omit for --all)
	molecule test \
		$(if $(SCENARIO),-s $(SCENARIO),--all --continue-on-failure) \
		--report

test: molecule ## Run the molecule test suite

collection-build: ## Build the collection tarball
	ansible-galaxy collection build --force

collection-install: collection-build ## Build and install the collection locally
	ansible-galaxy collection install $(COLLECTION_NAMESPACE)-$(COLLECTION_NAME)-*.tar.gz --force

clean: ## Remove build artefacts
	rm -f $(COLLECTION_NAMESPACE)-$(COLLECTION_NAME)-*.tar.gz
