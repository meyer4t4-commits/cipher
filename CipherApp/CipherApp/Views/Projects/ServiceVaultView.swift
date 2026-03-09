import SwiftUI

// MARK: - Service Vault View (API Keys & Tokens)

struct ServiceVaultView: View {
    let store: ProjectStore
    @Environment(\.dismiss) private var dismiss
    @State private var showAddCredential = false

    var body: some View {
        ZStack {
            CipherTheme.background.ignoresSafeArea()

            if store.credentials.isEmpty {
                emptyState
            } else {
                credentialsList
            }
        }
        .navigationTitle("Service Vault")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    showAddCredential = true
                } label: {
                    Image(systemName: "plus.circle.fill")
                        .font(.system(size: 18))
                        .foregroundColor(CipherTheme.accent)
                }
            }

            ToolbarItem(placement: .topBarLeading) {
                Button("Done") { dismiss() }
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(CipherTheme.accent)
            }
        }
        .sheet(isPresented: $showAddCredential) {
            AddCredentialSheet(store: store)
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: Spacing.lg) {
            Spacer()

            ZStack {
                Circle()
                    .fill(CipherTheme.accent.opacity(0.1))
                    .frame(width: 72, height: 72)
                Image(systemName: "key.fill")
                    .font(.system(size: 28, weight: .medium))
                    .foregroundColor(CipherTheme.accent)
            }

            VStack(spacing: Spacing.sm) {
                Text("No API keys stored")
                    .font(.system(size: 18, weight: .bold))
                    .foregroundColor(CipherTheme.textPrimary)

                Text("Store your API tokens here so agents can use them to interact with services like ElevenLabs, Railway, GitHub, and more.")
                    .font(.system(size: 14))
                    .foregroundColor(CipherTheme.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
            }

            Button {
                showAddCredential = true
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "plus")
                        .font(.system(size: 14, weight: .semibold))
                    Text("Add API Key")
                        .font(.system(size: 15, weight: .bold))
                }
                .foregroundColor(.white)
                .padding(.horizontal, 32)
                .padding(.vertical, 14)
                .background(CipherTheme.accent)
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
            }

            Spacer()
        }
    }

    // MARK: - Credentials List

    private var credentialsList: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(spacing: Spacing.sm) {
                // Group by service type
                ForEach(groupedCredentials, id: \.0) { serviceType, creds in
                    VStack(alignment: .leading, spacing: Spacing.xs) {
                        HStack(spacing: 6) {
                            Image(systemName: serviceType.icon)
                                .font(.system(size: 12))
                                .foregroundColor(serviceType.color)
                            Text(serviceType.rawValue)
                                .font(.system(size: 12, weight: .bold))
                                .foregroundColor(CipherTheme.textSecondary)
                        }
                        .padding(.horizontal, 4)

                        ForEach(creds) { credential in
                            CredentialRow(credential: credential, store: store)
                        }
                    }
                }
            }
            .padding(.horizontal, Spacing.lg)
            .padding(.top, Spacing.sm)
        }
    }

    private var groupedCredentials: [(ServiceType, [ServiceCredential])] {
        let grouped = Dictionary(grouping: store.credentials) { $0.serviceType }
        return grouped.sorted { $0.key.category < $1.key.category }
    }
}

// MARK: - Credential Row

struct CredentialRow: View {
    let credential: ServiceCredential
    let store: ProjectStore
    @State private var showToken = false
    @State private var copied = false

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(credential.name)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(CipherTheme.textPrimary)

                    Text(showToken ? credential.tokenValue : credential.maskedToken)
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundColor(CipherTheme.textSecondary)
                        .lineLimit(1)
                }

                Spacer()

                HStack(spacing: Spacing.sm) {
                    Button {
                        withAnimation { showToken.toggle() }
                    } label: {
                        Image(systemName: showToken ? "eye.slash" : "eye")
                            .font(.system(size: 13))
                            .foregroundColor(CipherTheme.textTertiary)
                    }

                    Button {
                        UIPasteboard.general.string = credential.tokenValue
                        copied = true
                        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                            copied = false
                        }
                    } label: {
                        Image(systemName: copied ? "checkmark" : "doc.on.doc")
                            .font(.system(size: 12))
                            .foregroundColor(copied ? CipherTheme.success : CipherTheme.textTertiary)
                    }

                    Button {
                        store.deleteCredential(credential.id)
                    } label: {
                        Image(systemName: "trash")
                            .font(.system(size: 12))
                            .foregroundColor(CipherTheme.error.opacity(0.7))
                    }
                }
            }

            if !credential.additionalFields.isEmpty {
                HStack(spacing: 8) {
                    ForEach(Array(credential.additionalFields.keys.sorted()), id: \.self) { key in
                        if let value = credential.additionalFields[key] {
                            HStack(spacing: 3) {
                                Text(key)
                                    .font(.system(size: 9, weight: .bold))
                                Text(value)
                                    .font(.system(size: 9))
                            }
                            .foregroundColor(CipherTheme.textTertiary)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(CipherTheme.background)
                            .clipShape(Capsule())
                        }
                    }
                }
            }
        }
        .padding(Spacing.md)
        .background(CipherTheme.surface)
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.sm)
                .stroke(CipherTheme.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
    }
}

// MARK: - Add Credential Sheet

struct AddCredentialSheet: View {
    let store: ProjectStore
    @Environment(\.dismiss) private var dismiss

    @State private var selectedService = ServiceType.elevenlabs
    @State private var name = ""
    @State private var tokenValue = ""
    @State private var additionalFields: [String: String] = [:]

    var body: some View {
        NavigationStack {
            ZStack {
                CipherTheme.background.ignoresSafeArea()

                ScrollView(.vertical, showsIndicators: false) {
                    VStack(alignment: .leading, spacing: Spacing.lg) {
                        serviceSelector
                        nameField
                        tokenField
                        additionalFieldsSection
                        saveButton
                    }
                    .padding(Spacing.lg)
                }
            }
            .navigationTitle("Add API Key")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Cancel") { dismiss() }
                        .foregroundColor(CipherTheme.textSecondary)
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }

    private var serviceSelector: some View {
        let grouped = Dictionary(grouping: ServiceType.allCases) { $0.category }
        let categoryOrder = ["AI & Generation", "Infrastructure", "Dev Tools", "Communication", "Social & Content", "Commerce", "Search", "Other"]

        return VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Service")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textSecondary)

            ForEach(categoryOrder, id: \.self) { category in
                if let services = grouped[category], !services.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(category)
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(CipherTheme.textTertiary)
                            .textCase(.uppercase)

                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 6) {
                            ForEach(services) { service in
                                Button {
                                    selectedService = service
                                    if name.isEmpty {
                                        name = "My \(service.rawValue) Key"
                                    }
                                } label: {
                                    VStack(spacing: 3) {
                                        Image(systemName: service.icon)
                                            .font(.system(size: 14))
                                        Text(service.rawValue)
                                            .font(.system(size: 9, weight: .semibold))
                                            .lineLimit(1)
                                            .minimumScaleFactor(0.8)
                                    }
                                    .foregroundColor(selectedService == service ? .white : CipherTheme.textSecondary)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 8)
                                    .background(selectedService == service ? service.color : CipherTheme.surface)
                                    .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
                                    .overlay(
                                        RoundedRectangle(cornerRadius: CornerRadius.sm)
                                            .stroke(selectedService == service ? Color.clear : CipherTheme.border, lineWidth: 1)
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    private var nameField: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Label")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textSecondary)
            TextField("e.g. My ElevenLabs Key", text: $name)
                .textFieldStyle(.plain)
                .font(.system(size: 15))
                .foregroundColor(CipherTheme.textPrimary)
                .padding(Spacing.md)
                .background(CipherTheme.surface)
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
        }
    }

    private var tokenField: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(selectedService.tokenLabel)
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textSecondary)
            TextField("Paste your \(selectedService.tokenLabel.lowercased()) here", text: $tokenValue)
                .textFieldStyle(.plain)
                .font(.system(size: 14, design: .monospaced))
                .foregroundColor(CipherTheme.textPrimary)
                .padding(Spacing.md)
                .background(CipherTheme.surface)
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()

            Text("Stored locally on your device. Agents use this to authenticate with \(selectedService.rawValue).")
                .font(.system(size: 11))
                .foregroundColor(CipherTheme.textTertiary)
        }
    }

    private var additionalFieldsSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            switch selectedService {
            case .elevenlabs:
                extraField(key: "voice_id", placeholder: "Voice ID (optional)")
            case .railway:
                extraField(key: "project_id", placeholder: "Railway Project ID (optional)")
            case .github:
                extraField(key: "repo", placeholder: "Default repo (optional, e.g. user/repo)")
            case .stripe:
                extraField(key: "webhook_secret", placeholder: "Webhook Secret (optional)")
            case .aws:
                extraField(key: "secret_key", placeholder: "Secret Access Key")
                extraField(key: "region", placeholder: "Region (e.g. us-east-1)")
            case .cloudflare:
                extraField(key: "account_id", placeholder: "Account ID (optional)")
            case .supabase:
                extraField(key: "project_url", placeholder: "Project URL (optional)")
            case .heygen:
                extraField(key: "avatar_id", placeholder: "Avatar ID (optional)")
            case .runway:
                extraField(key: "model", placeholder: "Model version (optional, e.g. gen-3)")
            case .slack:
                extraField(key: "channel", placeholder: "Default channel (optional, e.g. #general)")
            case .youtube:
                extraField(key: "channel_id", placeholder: "Channel ID (optional)")
            case .shopify:
                extraField(key: "store_url", placeholder: "Store URL (e.g. mystore.myshopify.com)")
            case .twilio:
                extraField(key: "account_sid", placeholder: "Account SID")
                extraField(key: "phone_number", placeholder: "From phone number")
            default:
                EmptyView()
            }
        }
    }

    private func extraField(key: String, placeholder: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(key.replacingOccurrences(of: "_", with: " ").capitalized)
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textSecondary)

            TextField(placeholder, text: Binding(
                get: { additionalFields[key] ?? "" },
                set: { additionalFields[key] = $0.isEmpty ? nil : $0 }
            ))
            .textFieldStyle(.plain)
            .font(.system(size: 14))
            .foregroundColor(CipherTheme.textPrimary)
            .padding(Spacing.md)
            .background(CipherTheme.surface)
            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
        }
    }

    private var saveButton: some View {
        Button {
            let credential = ServiceCredential(
                id: UUID().uuidString,
                name: name,
                serviceType: selectedService,
                tokenValue: tokenValue,
                additionalFields: additionalFields.compactMapValues { $0 },
                createdAt: Date(),
                lastUsedAt: nil
            )
            store.addCredential(credential)
            dismiss()
        } label: {
            HStack(spacing: 8) {
                Image(systemName: "key.fill")
                    .font(.system(size: 13))
                Text("Save to Vault")
                    .font(.system(size: 16, weight: .bold))
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(
                tokenValue.isEmpty || name.isEmpty
                ? Color.gray.opacity(0.5)
                : CipherTheme.accent
            )
            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
        }
        .disabled(tokenValue.isEmpty || name.isEmpty)
    }
}

#Preview {
    NavigationStack {
        ServiceVaultView(store: ProjectStore.shared)
    }
}
