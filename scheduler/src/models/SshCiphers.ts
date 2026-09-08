export interface SshCipherOption {
	value: string;
	label: string;
	detail: string;
}

/**
 * Curated subset of OpenSSH ciphers worth exposing for replication. Deprecated
 * CBC modes are deliberately omitted because modern OpenSSH servers no longer
 * offer them by default.
 */
export const SSH_CIPHER_OPTIONS: SshCipherOption[] = [
	{
		value: "",
		label: "Automatic (OpenSSH default)",
		detail:
			"Lets OpenSSH negotiate. Most builds pick ChaCha20-Poly1305 first, which is the slowest choice on CPUs that have AES-NI acceleration.",
	},
	{
		value: "aes128-gcm@openssh.com",
		label: "AES-128-GCM \u2014 fastest on modern CPUs",
		detail:
			"Single-pass authenticated encryption backed by AES-NI. Typically 25-30% faster than AES-128-CTR because it avoids the separate HMAC pass over the stream.",
	},
	{
		value: "aes256-gcm@openssh.com",
		label: "AES-256-GCM \u2014 fast, larger key",
		detail:
			"Same single-pass design as AES-128-GCM with a 256-bit key. Roughly 10-15% slower due to the extra AES rounds.",
	},
	{
		value: "aes128-ctr",
		label: "AES-128-CTR \u2014 widest compatibility",
		detail:
			"Encrypt-then-MAC, so every byte is processed twice: once by AES and once by HMAC-SHA2. Pick this only when the remote host does not offer a GCM cipher.",
	},
	{
		value: "aes256-ctr",
		label: "AES-256-CTR \u2014 widest compatibility, larger key",
		detail:
			"Same two-pass cost as AES-128-CTR with a 256-bit key. The slowest of the AES options on most hardware.",
	},
	{
		value: "chacha20-poly1305@openssh.com",
		label: "ChaCha20-Poly1305 \u2014 best without AES-NI",
		detail:
			"Software cipher that wins on older or ARM CPUs with no AES acceleration. On modern x86 it is slower than either GCM option.",
	},
];

export function sshCipherLabel(value: string): string {
	const trimmed = (value ?? "").trim();
	const match = SSH_CIPHER_OPTIONS.find((option) => option.value === trimmed);
	if (match) return match.label;
	return trimmed || "Automatic (OpenSSH default)";
}
