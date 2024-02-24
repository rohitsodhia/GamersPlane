import { siteLinkItems, loggedInLinkItems } from "./util";
import facebook from "/src/images/bodyComponents/facebook.svg";
import twitch from "/src/images/bodyComponents/twitch.svg";
import twitter from "/src/images/bodyComponents/twitter.svg";
import Image from "next/image";
import Link from "next/link";

export default function SiteFooter() {
    const linkDivClasses = "mb-2",
        linkClasses = "uppercase font-semibold";

    const aboutLinkItems: { [key: string]: string } = {
        FAQs: "/faqs",
        "About GP": "/about",
        "Contact Us": "/contact",
    };
    const socialLinkItems: { [key: string]: any[] } = {
        twitter: ["https://twitter.com/GamersPlane", twitter],
        facebook: ["https://www.facebook.com/GamersPlane/", facebook],
        twitch: ["http://www.twitch.tv/gamersplane", twitch],
    };
    const referralLinkItems: { [key: string]: string } = {
        Amazon: "http://amazon.com/?_encoding=UTF8&camp=1789&creative=9325&linkCode=ur2&tag=gampla0e6-20&linkId=7RQR4I66XH6Z2U4B",
        DriveThruRPG:
            "https://rpg.drivethrustuff.com/browse.php?affiliate_id=739399",
        "Easy Roller Dice Co.":
            "https://www.shareasale.com/r.cfm?B=751134&U=1218073&M=60247&urllink=",
        "Elderwood Academy":
            "https://www.elderwoodacademy.com/?utm_source=Gamers-Plane",
    };

    const siteLinks = Object.keys(siteLinkItems).map((title) => {
        return (
            <div key={title} className={linkDivClasses}>
                <Link href={siteLinkItems[title]} className={linkClasses}>
                    {title}
                </Link>
            </div>
        );
    });
    const aboutLinks = Object.keys(aboutLinkItems).map((title) => {
        return (
            <div key={title} className={linkDivClasses}>
                <Link href={aboutLinkItems[title]} className={linkClasses}>
                    {title}
                </Link>
            </div>
        );
    });
    const socialLinks = Object.keys(socialLinkItems).map((title, index) => {
        return (
            <div key={title} className={`${linkDivClasses}`}>
                <Link
                    href={socialLinkItems[title][0]}
                    className="block h-6 w-6"
                >
                    <Image src={socialLinkItems[title][1]} alt={title} />
                </Link>
            </div>
        );
    });
    const referralLinks = Object.keys(referralLinkItems).map((title) => {
        return (
            <div key={title} className={linkDivClasses}>
                <Link href={referralLinkItems[title]} className={linkClasses}>
                    {title}{" "}
                    {/* <span className="hidden md:inline">Referral Link</span> */}
                </Link>
            </div>
        );
    });

    return (
        <footer className="w-full p-2 xl:px-0 border-t-[6px] border-[#aaa]">
            <div className="flex w-full max-w-screen-xl mx-auto text-white gap-12 text-sm sm:text-base">
                <div className="hidden sm:block">{siteLinks}</div>
                <div>{aboutLinks}</div>
                {/* <div>{socialLinks}</div> */}
                <div className="grow text-right">
                    <h4
                        className={`${linkClasses} ${linkDivClasses} underline`}
                    >
                        Referral Links
                    </h4>
                    {referralLinks}
                    <form
                        action="https://www.paypal.com/donate"
                        method="post"
                        target="_top"
                    >
                        <input
                            type="hidden"
                            name="hosted_button_id"
                            value="6VHQ2BP4AS7L6"
                        />
                        <input
                            type="image"
                            src="/images/support_us.png"
                            name="submit"
                            title="PayPal - The safer, easier way to pay online!"
                            alt="Donate with PayPal button"
                        />
                        <img
                            alt=""
                            src="https://www.paypal.com/en_US/i/scr/pixel.gif"
                            width="1"
                            height="1"
                        />
                    </form>
                    <div>
                        <Link href="/acp/" className={linkClasses}>
                            ACP
                        </Link>
                    </div>
                </div>
            </div>
        </footer>
    );
}
