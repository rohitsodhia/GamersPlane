import { Open_Sans } from "next/font/google";
import localFont from "next/font/local";

export const open_sans = Open_Sans({
    subsets: ["latin"],
    variable: "--font-open-sans",
});
export const agency_fb = localFont({
    src: "../fonts/AgencyFB.woff",
    variable: "--font-agency-fb",
});

export const siteLinkItems: { [key: string]: string } = {
    Tools: "/tools",
    Systems: "/systems",
    Characters: "/characters",
    Games: "/games",
    Forums: "/forums",
    "The Gamers": "/gamers",
    Links: "links",
};
export const loggedInLinkItems = ["Characters", "The Gamers"];
