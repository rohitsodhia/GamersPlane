import Footer from "./footer";
import "./globals.css";
import Header from "./header";
import { Open_Sans } from "next/font/google";

const open_sans = Open_Sans({
    subsets: ["latin"],
});

export const metadata = {
    title: "Next.js",
    description: "Generated by Next.js",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en">
            <body className={`bg-body-black ${open_sans.className}`}>
                <Header />
                <div className="bg-white" style={{ height: "2000px" }}>
                    {children}
                </div>
            </body>
        </html>
    );
}
