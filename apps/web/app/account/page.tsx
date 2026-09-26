import type { Metadata } from "next";

import { AccountPage } from "@/components/account-page";

export const metadata: Metadata = { title: "Account · Canary Pact", description: "Review your Canary Pact identity and access level." };

export default function AccountRoute() { return <AccountPage />; }
