import EnterpriseWorkspaceShell from "./components/EnterpriseWorkspaceShell";

export default function WorkspaceLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <EnterpriseWorkspaceShell>{children}</EnterpriseWorkspaceShell>;
}
