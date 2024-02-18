import Footer from "./Footer";
import Header from "./Header";
import "./globals.css";
import { agency_fb, open_sans } from "./util";
import { headers } from "next/headers";

export const metadata = {
    title: "Next.js",
    description: "Generated by Next.js",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const path = headers().get("next-url");
    let top_margin = "mt-[70px]",
        max_width = "max-w-screen-xl",
        content_padding = "p-2 pt-3";
    if (!path || path === "/") {
        top_margin = "mt-[120px]";
        max_width = "w-full";
        content_padding = "";
    }

    return (
        <html lang="en">
            <body
                className={`bg-body-black ${open_sans.className} ${agency_fb.variable}`}
            >
                <Header />
                <main
                    className={`bg-white ${top_margin} ${content_padding} ${max_width}`}
                >
                    {children}
                </main>
                <Footer />
            </body>
        </html>
    );
}
