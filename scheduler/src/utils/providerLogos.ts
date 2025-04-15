interface ProviderLogo {
    logo: string;
    mainColor: string;
    hoverColor: string;
}

export const providerLogos: { [key: string]: ProviderLogo } = {
    "s3-AWS": {
        logo: "./img/s3-amazon.svg",
        mainColor: "#252F3E",
        hoverColor: "#13152D"
    },
    "s3-Wasabi": {
        logo: "./img/s3-wasabi.svg",
        mainColor: "#01CE3F",
        hoverColor: "#005B1C"
    },
    "s3-Ceph": {
        logo: "./img/s3-ceph.svg",
        mainColor: "#F05C56",
        hoverColor: "#9D2E1E"
    },
    "b2": {
        logo: "./img/backblaze.svg",
        mainColor: "#D2202F",
        hoverColor: "#610F16"
    },
    "dropbox": {
        logo: "./img/dropbox.svg",
        mainColor: "#0061FF",
        hoverColor: "#00235C"
    },
    "drive": {
        logo: "./img/google-drive.svg",
        mainColor: "#FF4329",
        hoverColor: "#DB1B00"
    },
    // "onedrive": {
    //     logo: "./img/onedrive.svg",
    //     mainColor: "#4F8AD8",
    //     hoverColor: "#1866AC"
    // },
    "google cloud storage": {
        logo: "./img/google-cloud.svg",
        mainColor: "#FA3B00",
        hoverColor: "#9E2500"
    },
    "azureblob": {
        logo: "./img/azure.svg",
        mainColor: "#00BCF2",
        hoverColor: "#004357"
    },
    "storj": {
        logo: "./img/Storj.svg",
        mainColor: "#00BCF2",
        hoverColor: "#1E90FF"
    },
    "s3-IDrive": {
        logo: "./img/IDrive.png",
        mainColor: "#00BCF2",
        hoverColor: "#1E90FF"
    }
};