import './globals.css';
import type { ReactNode } from 'react';
import { QueryProvider } from '../components/QueryProvider';

export const metadata = {
	title: 'Punjab Education Intelligence Platform',
	description: 'AI-powered education intelligence platform',
};

export default function RootLayout({ children }: { children: ReactNode }) {
	return (
		<html lang="en">
			<body>
				<QueryProvider>{children}</QueryProvider>
			</body>
		</html>
	);
}
