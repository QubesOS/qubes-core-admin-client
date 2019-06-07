RPM_SPEC_FILES := rpm_spec/qubes-core-admin-client.spec
ifneq ($(filter $(DISTRIBUTION), debian qubuntu),)
	DEBIAN_BUILD_DIRS := debian
	SOURCE_COPY_IN := source-debian-quilt-copy-in
endif
source-debian-quilt-copy-in:
	if [ $(DIST) == bionic ] ; then \
		sed -i '/python3-sphinx/a \ python3-xcffib,\n\ python3-daemon, ' $(CHROOT_DIR)/$(DIST_SRC)/debian/control ;\
	fi

